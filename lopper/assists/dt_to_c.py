#/*
#* Author:
#*       Valentin Monnot <vmonnot@outlook.com>
#*
#* SPDX-License-Identifier: BSD-3-Clause
#*/
import sys
import re
import yaml

from shutil         import rmtree
from lopper.tree     import *

sys.path.append(os.path.dirname(__file__) + "/baremetal")

# Is there a better way to achieve that ???
sys.path.append(os.path.dirname(__file__).rsplit("/", 2)[0] + "/py-dtbindings")

from bindings         import SDTBindings, Prop
from board_header     import BoardHeader

# A tuple of pattern we can find in node property name that we don't want in C struct.
non_processed_prop = ('#', '$', 'compatible', '-names', '-controller', '-parent', 'ranges')

def is_compat(node, compat_id):
    if re.search("baremetal_config,generate", compat_id):
        return baremetal_config_generator
    return ""

def baremetal_config_generator(tgt_node, sdt, options):
    # Set global verbose
    try:
        global verbose
        verbose    = options['verbose']
    except:
        verbose = 0

    # Set global path
    try:
        global path
        path = options['args'][0]
    except:
        print("[ERR] : First argument shall be path to build directory")
        return ""

    # Create build dir
    if not os.path.exists(path):
        os.mkdir(path)
    if not os.path.exists(path + "/include"):
        os.mkdir(path +"/include")

    root_node = sdt.tree[tgt_node]

    # Remove all disable nodes from the list
    global clean_node_list
    clean_node_list = get_active_node_list(root_node.subnodes())

    global mySDTBindings
    mySDTBindings = SDTBindings(verbose = verbose)

    global myBoardHeader
    myBoardHeader = BoardHeader(path)

    for node in clean_node_list:
        struct_generator(node)
        # platdata_generator(node)
        new_platdata_generator(node)
    myBoardHeader.close()

    return True


def check_status(node):
    """
    Check a node status and assume that node with no status are okay

        Parameters:
            node (lopper.tree.LopperNode): A node

        Return:
            status (str): The node status
    """
    status = ""
    try:
        status = node['status'].value[0]
    except:
        if verbose > 1:
            print("[WARN]: Node %s has no status, assuming it to be disabled"
            % node.name)
        status = "disabled"
    return status

def get_active_node_list(root_sub_nodes):
    """
    For each node check status and return a node list countaining all okay node
    that have max depth of 2 (max depth level is soc subnodes)

        Parameters:
            root_sub_nodes (list): A node list should be extracted from root node

        Returns:
            node_list (list): A only okay node list

        Remarks:
            Node over 2 of depth can still be accessed using .subnodes() method
            We will do it like that because these subnodes should be processed
            another way.
    """
    node_list = list()
    for node in root_sub_nodes:
        #Check if node is enable or not so that we know if we process it
        status = check_status(node)
        if (status == "okay" or status == "ok") and node.depth <= 2:
            node_list.append(node)
    return node_list


def struct_generator(node, return_struct = False):
    """
    Used to generate C struct for the given node

        Parameters:
            node (lopper.tree.LopperNode): The node you want to generate struct for
            return_struct          (bool): If true, generated struct will be returned
                                           Instead of being added to myBoardHeader

        Returns:
            (str) | (dict): The name of the generated struct or the generated struct
    """
    struct_name = node.type[0].replace(',','_').replace('-','_')

    myBinding = mySDTBindings.get_binding(node.type[0])
    if myBinding:
        # TODO: We should check required nodes to ensure that tree is well written

        typedef_t = "typedef struct %s_s %s_S;\n" % (struct_name,
                                                     struct_name.upper())
        struct_t = dict()
        property_t = dict()

        properties = myBinding.required()
        for i in range(2):
            for property in properties:
                if not any(x in property for x in non_processed_prop):
                    myProp = myBinding.get_prop_by_name(property)

                    if not myProp:
                        # FIXME: py-dtbindings do not handle patternProperties
                        continue

                    prop_struct = _struct_generator(node, myProp,node.name.split('@')[0])
                    if not prop_struct: continue

                    if i == 1:
                        # In case we are fetching optional, we will redo the
                        # dict so that we can include a presence flag.
                        # There is only one entry in this dict.
                        # We extract the only key so that
                        # the next instruction wont be too long
                        key_t = list(prop_struct.keys())[0]
                        prop_struct[key_t] = { "type"       : prop_struct[key_t],
                                               "presence"   : False}
                    property_t.update(dict(prop_struct))

            if i == 0:
                struct_t.update({"required" : property_t})
                properties = myBinding.optional()
                property_t = dict()
            else:
                struct_t.update({"optional" : property_t})

        if return_struct: return struct_t
        # Else
        myBoardHeader.add2struct({struct_name : struct_t})
        myBoardHeader.add2typedef(typedef_t)
        return struct_name.upper() + '_S *'
    return None

def _struct_generator(node, myProp, node_name):
    """
    Will be called by struct_generator to generate a dict that contains
    all necessary informations for a given node.
    These informations are extracted from dt-bindings

        Parameters:
            myProp (bindings.MainProp): The binding informations for the given node
                                        Extracted from py-dtbindings
            node_name    (str): The of the node (should be the str before the @)

        Returns:
            A dict with poperty name as key and type as value or None
    """
    # List means multiple var for this property
    if type(myProp.type) == list:
        struct_t = dict()
        for item in myProp.type:
            struct_tt.update({item[1] : item[0]})
        return {myProp.name : struct_t}

    # Tuple means that there is different type possible
    elif type(myProp.type) == tuple:
        type_t = check_type(node,node_name,myProp)
        return {myProp.name : type_t}

    # Means type is str but for now we don't process some specific nodes
    elif not myProp.type in ("unknown","none","name","object"):
        return {myProp.name : myProp.type}
    return None


def new_platdata_generator(myNode):
    """
                                [WIP]
    Replacement for platdata_generator() including optional properties
    """
    main_name = myNode.name.replace('@','_').replace('-','_').upper()
    if main_name in myBoardHeader.const_keys():
        # platdata already generated for this node
        # We can fall here for node that phandle is used in different node
        # e.g. clock controller or interrupt controller
        return main_name

    for node in myNode.subnodes():
        name = node.name.replace('@','_').replace('-','_').upper()
        struct_name = node.type[0].replace(',','_').replace('-','_')
        nodeStruct = myBoardHeader[struct_name]

        # Will be used in case the struct as already been modified
        # We will compare the modified one with the newly modified one
        # If both are the same, so no problem
        # If their differents, we must rename and keep both
        modified = False

        if not nodeStruct:
            # Normally, the first node of the subnodes list is the main node
            # If myBoardHeader return None instead of a struct, that means
            # no struct had been generated for it in  struct_generator so exit
            if node == myNode:
                return None

            else:
                # TODO
                # We should generate a struct for these nodes but, there's often
                # No compatible in object node so struct_generator won't work
                # on these nodes currently
                # py-dtbindings need to be updated to support patternProperties
                # That's generally where object info are
                continue
        else:
            # We should compare the struct returned by myBoardHeader with the
            # original struct to ensure that struct has not already been modified
            # If it has been modified, that's mean another node use the same struct
            # Because it had the same compatible.
            # So we should process using the original struct and compare both
            # struct at the end of the process.
            # This way, if two node with the same compatible have not the same
            # optional, we will make two different struct for each.

            original = struct_generator(node, True)
            if nodeStruct != original:
                modified = True
                nodeStruct = original

        properties = "required"
        platdata = {'type'      :  struct_name + '_s',
                    'required'  :  dict(),
                    'optional'  :  dict()}
        for i in range(2):
            if i:
                properties = "optional"

            # All necessary struct update should be done on this tmp one
            structCpy = nodeStruct.copy()
            for key, type_t in nodeStruct[properties].items():

                extern_t = "extern const %s %s;\n" % (struct_name,name)

                if i:
                    type_t = type_t['type']

                generated = _new_platdata_generator(node, key, type_t, name)

                if not generated:
                    continue

                # Update type on the tmp struct
                if generated[1]:
                    if i:
                        structCpy['optional'][key]['type'] = generated[1]
                    else:
                        structCpy['required'][key] = generated[1]

                # Set presence to True if optional
                if i:
                    structCpy['optional'][key]['presence'] = True
                platdata[properties].update(generated[0])

        if platdata['required']:
            myBoardHeader.add2const(platdata, name)
    return main_name


def _new_platdata_generator(node, key, type_t, name):
    """
    Will be called by platdata_generator to generate platdata for the given prop

        Parameters:
            node (lopper.tree.LopperNode): The node you want to generate platdata for
            key                     (str): The key of the property
            type_t                  (str): The type of the property
            names                   (str): The name of the node formated

        Returns:
            (tuple( dict , str )):  ({ key : value}, type)
                                    type: Only if type has been modified

    """
    myBinding = mySDTBindings.get_binding(node.type[0])
    if not myBinding:
        return None

    myProp = myBinding.get_prop_by_name(key)

    try:
        myNodeProp = node[key]
    except KeyError:
        # Item name might follow a pattern
        key_t = ''
        for item in node:
            prop_t = myBinding.get_prop_by_name(item.name)
            if prop_t:
                if prop_t.name == myProp.name:
                    key_t = item.name
                    break
        if not key_t:
            # FIXME:
            if key == "interrupts":
                key_t = "interrupts-extended"
            else:
                return None
        myNodeProp = node[key_t]

    # Now that we have our basis, we have to generate plat data depeding on type
    if type_t == 'void *':
        # phandle or object, generate struct
        generated = _phandle_processor(myNodeProp, node)
        if generated:
            print(generated)
            return ({key : generated[0]}, generated[1])
        return None

    elif '*' in type_t:
        # Array or matrix
        if len(myNodeProp.value) == 1:
            new_type = None
            if "**" in type_t:
                new_type = type_t.replace('**','*')
            return ({key : hex(myNodeProp.value[0])}, new_type)
        else:
            # We msut search if there is any properties that define the number of
            # cells.
            if key == "reg":
                toFind = "#address-cells"
            elif key == "interrupts":
                if myNodeProp.name == "interrupts-extended":
                    generated = _phandle_processor(myNodeProp, node)
                    if generated:
                        print(generated)
                        return ({key : generated[0]}, generated[1])
                    return None
                toFind = "interrupt-parent"
            else:
                toFind = None

            size = 1
            if toFind:
                # Now we will search in the node and parent node the property
                # we have to find.
                tmp_node = node
                while not toFind in tmp_node.keys():
                    if not tmp_node.parent:
                        print("[ERR ]: No %s found for %s." % (toFind,node.name))
                        print("[ERR ]: No more parent node left to find it.")
                        print("[ERR ]: Is your tree complete ?")
                        sys.exit(-1)
                    tmp_node = tmp_node.parent

                # And with that we can update the size of each elements of the
                # property in order to generate an array or a matrix for it.
                if key == "reg":
                    size = (tmp_node["#address-cells"].value[0] +
                            tmp_node["#size-cells"].value[0])

                elif key == "interrupts":
                    interrupt_parent = node.tree.pnode(tmp_node["interrupt-parent"].value[0])
                    size = interrupt_parent["#interrupt-cells"].value[0]

            array = _array_generator(name, key, type_t, myNodeProp.value, size)
            gen_name = key.upper().replace('-','_').replace(',','_') + "_" + name

            new_type = None
            if "**" in type_t:
                new_type = type_t.replace('**','*')

            if array[1]:
                new_type = { key + ("[%i]" % size) : new_type}

            myBoardHeader.add2generated(array[0])
            return ({key : gen_name}, new_type)


    if type_t == 'bool':
        return ({key : 1}, None)
    return ({key : hex(myNodeProp.value[0])}, None)

def _phandle_processor(myNodeProp, node):
    if len(myNodeProp.value) == 1:
        # Get the node and try to gen a struct for it
        pnode = node.tree.pnode(myNodeProp .value[0])
        struct = struct_generator(pnode)

        if not struct:
            return None
        # Generate platdata for it
        name = new_platdata_generator(pnode)
        return (name, struct)

    name_t = str()
    if myNodeProp.name[-1] == "s":
        name_t = "#" + myNodeProp.name[:-1] + "-cells"
    elif myNodeProp.name == "interrupts-extended":
        name_t = "#interrupt-cells"

    pnode = node.tree.pnode(myNodeProp.value[0])
    if name_t:
        return None

    else:
        # We don't have any informations on number of cells
        # We will suppose that only the first value is a phandle
        # And all others values are attached values
        ###
        # First, try to generate a struct for the pnode
        struct = struct_generator(pnode)

        if not struct:
            return None
        # Generate platdata for it
        name = new_platdata_generator(pnode)

        gen_name = myNodeProp.name.replace(',','_').replace('-','_')

        # Now process the value(s) attache to the phandle...
        if len(myNodeProp.value[1:]) == 1:
            # Only one value attached to the phandle
            value = myNodeProp.value[1]
            type_t = 'uint32_t'

        else:
            # Multiple values attached to phandle
            # Generate array with values
            # Necessary name for _array_generator
            node_name = node.name.replace('@','_').replace('-','_').upper()

            # Assuming uint32_t as default type
            type_t = 'uint32_t *'
            # Generating array and add it to generated
            generated = _array_generator(node_name, gen_name,
                                         type_t, myNodeProp.value[1:])
            myBoardHeader.add2generated(generated[0])
            # Update value with the name of array
            value = gen_name.upper() + '_' + node_name

        name = {gen_name             : name,
                gen_name + '_value'  : value}
        struct = {gen_name              : struct,
                  gen_name + '_value'   : type_t}
        return(name, struct)

def _array_generator(name, key, type_t, value, size = 1):
    """
    Genetate C array for platdata_generator()

        Parameters:
            type_t  (str): The type of the future array
            key     (str): The name of the property
            name    (str): The name of the struct you generate a array for
            myNodeProp (lopper.tree.LopperProp): The properties from devicetree
                                                 to fill in the araay
            size    (int): Size from size-cells + address-cells if needed
                           This is used in case we have 2D array

        Returns:
            (tuple):    Return the generated array and True if 2D array

    """
    generated = "const %s" % type_t.replace('*','')
    if size == 1 or size >= len(value):
        generated += "%s_%s[%i] = {" % (key.upper().replace('-','_').replace(',','_'),
                                        name,len(value))
        for val in value:
            generated += str(hex(val)) + " , "
        # End the line and remove the last " , "
        return (generated[:-3] + "};\n", False)

    else:
        generated += ("%s_%s[%i][%i] = {{" %
                      (key.upper(),name,len(value)/size,size))
        for x, val in enumerate(value):
            if x % size == 0 and x != 0:
                generated = generated[:-3]
                generated += "},{"
            generated += str(hex(val)) + " , "
        # End the line and remove the laste " , "
        return (generated[:-3] + "}};\n", True)

def platdata_generator(node):
    """
    This function will try to generate a declaration based on a struct for the given node

        Parameters:
            node (lopper.tree.LopperNode): The node you want to generate platdata for
    """
    nodeStruct = myBoardHeader[node.name.split('@')[0]]
    if nodeStruct:
        name = node.name.replace('@','_').replace('-','_').upper()

        struct_name = node.name.split('@')[0].upper() + "_S"
        myBoardHeader.add2extern("extern const %s %s;\n" % (struct_name,name))
        const_t = {'type' : struct_name, 'values' : dict()}

        nodeStructDict = nodeStruct.copy()
        for key, type_t in nodeStructDict.items():
            if not type_t:
                print(nodeStruct)
            if any(pattern in key for pattern in ("-names","-controller")):
                continue

            myBinding = mySDTBindings.get_binding(node['compatible'].value[0])
            if not myBinding:
                # FIXME: py-dtbindings do not handle patternProperties
                const_t = None
                continue

            myProp = myBinding.get_prop_by_name(key)

            try:
                myNodeProp = node[key]
            except KeyError:
                # Item name might follow a pattern
                key_t = ''
                for item in node:
                    prop_t = myBinding.get_prop_by_name(item.name)
                    if prop_t:
                        if prop_t.name == myProp.name:
                            key_t = item.name
                            break
                if not key_t:
                    # FIXME:
                    if key == "interrupts":
                        key_t = "interrupts-extended"
                myNodeProp = node[key_t]

            # Now, generate plat data depending of type
            if type_t == 'void *':
                # Void * means a phandle or a sub object
                # To process that case, we should generate a new struct

                ret = _generate_sub_struct(myNodeProp, node)
                if ret:
                    const_t['values'].update(ret)

            elif '*' in type_t:
                if '**' in type_t:
                    prop_t = myProp['maxItems']
                    if prop_t and prop_t.value == 1:
                    # In case bindings explicitly say that maxItems = 1
                    # We are facing 1D array
                        if prop_t.value == 1:
                            type_t = type_t.replace('**','*')
                            myBoardHeader.update_type(node.name.split('@')[0],
                                                      key, type_t)
                            # Simple array
                            _generate_simple_array(type_t, key ,name, myNodeProp)
                            const_t['values'].update({key : "%s_%s" % (key.upper(),name)})

                    # We might be facing 2D array we must check using #*-cells property
                    else:
                        toFind = str()

                        if key == "reg":
                            toFind = "#address-cells"
                        elif key == "interrupts":
                            if myNodeProp.name == "interrupts-extended":
                                # Generate sub struct for phandle in interrupts
                                ret = _generate_sub_struct(myNodeProp, node)
                                if ret:
                                    const_t['values'].update(ret)
                                continue
                            # Else
                            toFind = "interrupt-parent"
                        else:
                            # I Actually didn't saw any node falling here
                            # Maybe there is something to implemente here
                            print("[NIY ]: Property %s for node %s not processed" %
                                  (key, node.name))
                            const_t["values"].update({key : "NULL"})
                            continue

                        tmp_node = node
                        while not toFind in tmp_node.keys():
                            if not tmp_node.parent:
                                print("[ERR ]: No %s found for %s." % (toFind,node.name))
                                print("[ERR ]: No more parent node left to find it.")
                                print("[ERR ]: Is your tree complete ?")
                                sys.exit(-1)
                            tmp_node = tmp_node.parent

                        size = int()
                        if key == "reg":
                            size = (tmp_node["#address-cells"].value[0] +
                                    tmp_node["#size-cells"].value[0])
                        elif key == "interrupts":
                            interrupt_parent = node.tree.pnode(tmp_node["interrupt-parent"].value[0])
                            size = interrupt_parent["#interrupt-cells"].value[0]

                        type_t = type_t.replace("**","*")
                        myBoardHeader.update_type(node.name.split('@')[0], key, type_t)

                        if len(node[key].value) == size:
                            _generate_simple_array(type_t, key, name, myNodeProp)
                        else:
                            _generate_simple_array(type_t, key, name, myNodeProp, size)
                        const_t['values'].update({key : "%s_%s" % (key.upper(),name)})

                else:
                    # Simple array
                    if len(myNodeProp.value) == 1:
                        myBoardHeader.update_type(node.name.split('@')[0], key, type_t.replace('*',''))
                        const_t['values'].update({key : myNodeProp.value[0]})
                    else:
                        _generate_simple_array(type_t, key ,name, myNodeProp)
                        const_t['values'].update({key : "%s_%s" % (key.upper(),name)})

            elif isinstance(type_t,dict):
                # Multiple type for the given node
                # Or struct may already have been modified
                i = 0
                for k, v in type_t.items():
                    #print(k,v)
                    if not '*' in v:
                        pass
                    elif "void" in v:
                        ret = _generate_sub_struct(myNodeProp, node)
                        if ret:
                            const_t['values'].update(ret)
                    i += 1

            else:
                pass
        if const_t:
            print(const_t)
            myBoardHeader.add2const(const_t, name)


def _generate_simple_array(type_t, key ,name, myNodeProp, size = 0):
    """
    Genetate C array for platdata_generator()

        Parameters:
            type_t  (str): The type of the future array
            key     (str): The name of the property
            name    (str): The name of the struct you generate a array for
            myNodeProp (lopper.tree.LopperProp): The properties from devicetree
                                                 to fill in the araay
            size    (int): Size from size-cells + address-cells if needed
                           This is used in case we have 2D array

    """
    generated = "const %s" % type_t.replace('*','')
    if size == 0 or size >= len(myNodeProp.value):
        generated += "%s_%s[%i] = {" % (key.upper(),name,len(myNodeProp.value))
        for val in myNodeProp.value:
            generated += str(hex(val)) + " , "
        # End the line and remove the last " , "
        generated = generated[:-3] + "};\n"

    else:
        generated += ("%s_%s[%i][%i] = {{" %
                      (key.upper(),name,len(myNodeProp.value)/size,size))
        for x, val in enumerate(myNodeProp.value):
            if x % size == 0 and x != 0:
                generated = generated[:-3]
                generated += "},{"
            generated += str(hex(val)) + " , "
        # End the line and remove the laste " , "
        generated = generated[:-3] + "}};\n"
        # Update type
        struct_name = name.lower().rsplit("_",1)[0].replace("_","-")
        myBoardHeader[struct_name][key] = { key + ("[%i]" % size) : type_t}


    myBoardHeader.add2generated(generated)

def _generate_sub_struct(myNodeProp, node):
    """
    Generate C struct for struct_generator()

        Parameters:
            myNodeProp (lopper.tree.LopperProp): The property of the node you want
                                                 to generate a sub struct for
            node       (lopper.tree.LopperNode): The node which have this property

        Returns:
            const_t (dict): A dict which contains the generated struct

        Known issues:
            In case there is 2 phandle in a property and those 2 phandle
            are different but has the same type of struct (or not) the
            second struct is ignored. Some mod needs to be done in this
            function and also in board_header.py I think.
    """
    # void * means phandle, so first arg should be a phandle
    phandle_node = node.tree.pnode(myNodeProp.value[0])

    # Search for phandle cells number
    name_t = str()
    if myNodeProp.name[-1] == "s":
        name_t = "#" + myNodeProp.name[:-1] + "-cells"
    elif myNodeProp.name == "interrupts-extended":
        name_t = "#interrupt-cells"

    items_t = list()
    i = 0

    # If there is a defined number of cells for the first phandle
    if name_t:
        # This while loop will make a list that's look like the array in the dt
        # Because it will always look like [val_1,val_2,val_3,val_4]
        # whenever we have:
        #  mynode = <val_1 val_2> , <val_3 val_4>
        # or
        #  mynode = <val_1 val_2 val_3 val_4>
        while i < len(myNodeProp.value):
            if name_t in phandle_node.keys():
                # array = <phandle , value_0 , ... , value_n>
                cells = phandle_node[name_t].value[0] + 1
                if cells == 1:
                    items_t.append(myNodeProp.value[i])
                else:
                    items_t.append(myNodeProp.value[i:i+cells])
                # Jump to the next phandle
                i += cells
                if i < len(myNodeProp.value):
                    # Check for next phandle cells number in case it's different
                    phandle_node = node.tree.pnode(myNodeProp.value[i])

            else:
                items_t.append(myNodeProp.value[i])
                i += 1
                if i < len(myNodeProp.value):
                    # Check for next phandle cells number in case it's different
                    phandle_node = node.tree.pnode(myNodeProp.value[i])
    del name_t

    if items_t:
        name_t  = str()
        const_t = dict()
        # Type would be update later
        pnode_name = node.tree.pnode(myNodeProp.value[0]).name.split("@")[0].replace("-","_")
        type_t     = { pnode_name : "void *"}

        # node_name will be used to name generated struct elements
        node_name = myNodeProp.name.replace("-","_")

        # Check if names exist in the devicetree
        if myNodeProp.name[-1] == "s":
            # If there is a "s" at the end of the node name we have to remove it
            name_t = myNodeProp.name[:-1] + "-names"
        elif myNodeProp.name == "interrupts-extended":
            # interrupts-extended and interrupts have the same name node
            name_t = "interrupt-names"
            node_name = "interrupts"

        # Check in the devicetree if a *****-names prop exist
        if name_t in node.keys():
            name_t = node[name_t].value



        if not len(name_t) == len(items_t):
            # We should have name if multiple items
            name_t = list()
            for i in range(len(items_t)):
                name_t.append(node_name + "_%i" %i)

        for id, item in enumerate(items_t):
            name = (node_name + "_" + name_t[id].replace("-","_"))
            if isinstance(item,int):
                # Only phandle no value attached
                # struct generation
                pnode = node.tree.pnode(item)
                struct_name = struct_generator(pnode)
                type_t.update({pnode.name.split("@")[0].replace("-","_") : struct_name})
                platdata_generator(pnode)

            else:
                # phandle + value(s)
                # struct generation
                pnode = node.tree.pnode(item[0])
                struct_name = struct_generator(pnode)
                type_t.update({pnode.name.split("@")[0].replace("-","_") : struct_name})
                platdata_generator(pnode)

                if len(item) > 2:
                    # Generating an array because there is at list 2 values
                    # attached to the phandle
                    name_gen = (node.name.upper().replace("-","_").replace("@","_") +
                                "_" + node_name.upper() + "_" +
                                name_t[id].upper().replace("-","_"))

                    generated = "const uint32_t %s[%i] = {" %(name_gen,len(item)-1)

                    for value in item[1:]:
                        generated += "%s , " % hex(value)
                    generated = generated[:-3] + "};\n"
                    myBoardHeader.add2generated(generated)

                    const_t.update({ name : name_gen})
                    type_t.update({ name : "uint32_t *"})

                else:
                    # Only one value attached to the phandle, no need to generate
                    # an array for it. A simple uint32 will work.
                    const_t.update({name : hex(item[1])})
                    type_t.update({ name : "uint32_t"})

        if myNodeProp.name == "interrupts-extended":
            myBoardHeader.update_type(node.name.split('@')[0], "interrupts", type_t)
        else:
            myBoardHeader.update_type(node.name.split('@')[0], myNodeProp.name, type_t)
        if const_t: return const_t
    else:
        return None


#   Used to check size for node that have different type possible.
#   This way we can determine which type to use in struct.
#   Used by check_type()
#   Warning    This might not be the cleanest way. Any suggestion ?
type_size = {   'bool'  : 1                 ,
                '8'     : 0xFF              ,
                '16'    : 0xFFFF            ,
                '32'    : 0xFFFFFFFF        ,
                '64'    : 0xFFFFFFFFFFFFFFFF}

def check_type(node, node_name,node_prop):
    """
    If there is different type possible from a Prop, will check every instance
    of this prop to determine which type use.

    This function admit that there is only 2 differents type in for the given property
    (as it is in all actual binding).
    Also, it admit that types are sorted by their size.

        Parameters:
            node           : The node
            node_name (str): The node name we want to determine type
            node_prop (bindings.MainProp): The node poperties that contains types list

        Returns:
            (str): A type (e.g. uint32_t)
    """
    list_t = []
    # First, make a list of every node that use the same struct (and has the same name)
    for node_t in clean_node_list:
        if node_name in node_t.name:
            list_t.append(node_t)

    if not list_t:
        list_t.append(node)
    # Normally their should always be at least one item but, we never know

    # If we fall here, then list should look like (void*,object)
    # So we don't have to test, only return void*
    if "void" in node_prop.type:
        return "void *"

    if re.findall(r'\d+',node_prop.type[0]):
        a = re.findall(r'\d+',node_prop.type[0])[0]
    else:
        # Normally it's bool, if it's char* or char** then...
        # Then I never saw that case !
        # If it happen, script will crash because of KeyError
        # And so we might figure out how to process the given node
        a = node_prop.type[0]

    if re.findall(r'\d+',node_prop.type[1]):
        b = re.findall(r'\d+',node_prop.type[1])[0]
    else:
        # Same
        b = node_prop.type[1]
    size_t = [type_size[a],type_size[b]]
    for node_t in list_t:
        try:
            item = node_t[node_prop.name]
        except KeyError:
            # TODO
            item = None

        if item:
            for value in item.value:
                # If int  value goes from -0x80* to 0x7F*
                if "uint" in node_prop.type:
                    if value >= size_t[0]:
                        return node_prop.type[1]
                # Else, it goes 0x0 to 0xF*
                else:
                    if value >= 0:
                        if value >= size_t[0]/2:
                            return node_prop.type[1]
                    else:
                        if value <= -size_t[0]/2:
                            return node_prop.type[1]
    # No return in for loop means value fit in first
    return node_prop.type[0]
