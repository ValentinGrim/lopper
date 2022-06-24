#/*
#* Author:
#*       Valentin Monnot <vmonnot@outlook.com>
#*
#* SPDX-License-Identifier: BSD-3-Clause
#*/

import sys
from copy import deepcopy

class BoardHeader:
    def __init__(self, path, optional_mode = None):
        """
        This class intend to be used to as a writter.

            Parameters:
                path (str): The path where output files should be generated.
                optional_mode (str): The way we wan't to write optional prop
                                     Should be:
                                     - None     : No optional
                                [NYI]- boolean  : Optional are written to struct
                                                  alongside a bool telling if
                                                  optional prop is present
                                [WIP]- define    : Only present optional are part
                                                  of the struct and #define are
                                                  written as indicator for the soft

            Internal vars:
                _typdef (list): This list will contains all typedef definition.
                                Used to be written in board_header.h.
                _extern (list): This list will contains all extern definition.
                                Used to be written in board_header.h.
                _struct (ditc): This dict will contains all struct definition.
                                Used to be written in board_header.c.
                _const  (dict): This dict will contains all struct declaration.
                                Used to be written in board_header.c.
                _generated (list): This list will contains all generated tab.
                                Used to be written in board_header.c to fill
                                struct declaration internals vars.
        All these internals should be filled or retrieve using getters/setters.
        """
        try:
            self._header = open(path + "/include/board_header.h", "w")
        except OSError as err:
            print("[ERR ]: Unable to open file %s, %s" % (path + "/include/board_header.h" ,err))
            sys.exit(-1)

        try:
            self._source = open(path + "/board_header.c", "w")
        except OSError as err:
            print("[ERR ]: Unable to open file %s, %s" % (path + "/board_header.c" ,err))
            sys.exit(-1)

        # Header
        self._typedef     = list()
        self._extern    = list()
        # Source
        self._struct    = dict()
        self._const        = dict()
        self._generated = list()

        self.optional_mode = optional_mode

        self._header.write("""/*
 * This file has been automatically generated using lopper
 * @script        dt_to_c.py
 */

#ifndef __BOARD_HEADER_H__
#define __BOARD_HEADER_H__

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
""")
        self._source.write("""/*
 * This file has been automatically generated using lopper
 * @script        dt_to_c.py
 */

#include "board_header.h"
""")

    def __getitem__(self, name):
        """
        Magic method that return an item from self._struct if exist
        """
        if name in self._struct.keys():
            return deepcopy(self._struct[name])
        return None

    def add2struct(self, struct):
        """
        Setter for internal _struct
        """
        self._struct.update(struct)


    def struct_keys(self):
        return self._struct.keys()

    def add2typedef(self, typedef):
        """
        Setter for internal _typedef
        """
        if not typedef in self._typedef:
            self._typedef.append(typedef)

    def add2extern(self, extern):
        """
        Setter for internal _extern
        """
        if not extern in self._extern:
            self._extern.append(extern)

    def add2generated(self, generated):
        """
        Setter for interanl _generated
        """
        if not generated in self._generated:
            self._generated.append(generated)

    def add2const(self, const, name):
        """
        Setter for internal _const
        """
        if not name in self._const.keys():
            self._const.update({name : const})

    def const_keys(self):
        return self._const.keys()

    def update_type(self, name, key, type_t):
        """
        By default, internal _struct will contains type and name for any elements.
        When an element is pointing on a phandle, default type use to be "NULL".
        If we generate a struct for this phandle, type should be updated to match
        the type of the freshly generated struct.

            Parameters:
                name    (str): The name of the struct
                key     (str): The element of the struct
                type_t  (any): The new type for the element
        """
        if isinstance(type_t, dict):
            for k,v in self._struct[name].items():
                if isinstance(v, dict):
                    if any(keys in v.keys() for keys in type_t.keys()):
                        if len(type_t) == 1:
                            return
                        else:
                            tmp = set(v.keys())
                        del type_t[list(tmp.intersection(type_t.keys()))[0]]
        self._struct[name][key] = type_t

    def close(self):
        """
        This function has to be called at the end of the process.
        It will write all internals vars into the .c / .h files and close them.
        """
        # Header
        self._header.write('\n')
        for typedef in sorted(self._typedef):
            self._header.write(typedef)

        self._header.write('\n')

        for extern in sorted(self._extern):
            self._header.write(extern.replace("-","_"))

        self._header.write('\n')

        # Source
        if self.optional_mode == 'boolean':
            self._optional_processor()

        sorted_struct = self._struct_sorter()

        self._source.write('\n')
        for struct_n, struct_v in sorted_struct.items():
            self._source.write("struct %s_s{\n" % struct_n.replace("-","_"))
            for item in struct_v:
                if type(item[0]) == tuple:
                    if self.optional_mode == 'boolean':
                        self._source.write("    const %s %s;\n" % (item[0][0],
                                                                   item[1]))
                    elif self.optional_mode == 'define':
                        if item[0][1]:
                            self._header.write("#define %s_%s\n" % (struct_n.upper(),
                                                                 item[1].upper()))
                            self._source.write("    const %s %s;\n" % (item[0][0],
                                                                       item[1]))
                else:
                    self._source.write("    const %s %s;\n" % item)
            self._source.write("};\n")

        self._source.write('\n')

        for generated in sorted(self._generated):
            self._source.write(generated)

        self._source.write('\n')

        for const_n, const_v in self._const.items():
            type_t = const_v["type"].replace("-","_")
            self._source.write("const %s %s = {\n" % (type_t,const_n.replace("-","_")))

            properties = 'required'
            for i in range(2):
                for name, value in const_v[properties].items():
                    if type(value) == dict:
                        for k,v in value.items():
                            self._source.write("    .%s = %s,\n" % (k,v))
                    else:
                        self._source.write("    .%s = %s,\n" %
                                          (name.replace(',','_').replace('-','_'), value))

                if self.optional_mode in ('boolean','define'):
                    properties = 'optional'
                else:
                    break

            self._source.write("};\n")

        self._source.close()

        self._header.write('\n#endif // __BOARD_HEADER_H__')
        self._header.close()

    def _optional_processor(self):
        """
        If optional mode is boolean, generate boolean that should indicate
        presence of each optional properties.
        """
        optional = dict()
        for struct_n, struct_v in self._struct.items():
            for name, type_t in struct_v['optional'].items():
                if type_t['type'] != 'bool':
                    struct_v['required'].update({name + '_p' : 'bool'})

    def _struct_sorter(self):
        """
        Sort self._source by type to avoid padding

            Returns:
                struct (dict): A new struct based on self._source, sorted
        """
        struct = dict()
        for struct_n, struct_v in sorted(self._struct.items()):
            order = {'64' : list(), '*' : list(), '32' : list(), '16' : list(),
                     '8' : list(), 'char' : list(), 'bool' : list()}
            # Dual loop in order to fetch req + opt
            properties = "required"
            for i in range(2):
                for name, type_t in struct_v[properties].items():
                    # This big if elif else could be reworked more clean
                    if i == 0 and type(type_t) == dict:
                        # Required + dict
                        for k,v in type_t.items():
                            if '*' in v:
                                key = "*"
                            else:
                                key = [key for key in order.keys() if key in v]
                                key = key[0]
                            order[key].append((k , v))
                    elif i == 1:
                        # Optional
                        if type(type_t['type']) == dict:
                            for k,v in type_t['type'].items():
                                if '*' in v:
                                    key = "*"
                                else:
                                    key = [key for key in order.keys() if key in v]
                                    key = key[0]
                                order[key].append((k , (v , type_t['presence'])))
                        else:
                            if '*' in type_t['type']:
                                key = "*"
                            else:
                                key = [key for key in order.keys() if key in type_t['type']]
                                key = key[0]
                            order[key].append((name ,
                                              (type_t['type'] ,
                                               type_t['presence'])))
                    else:
                        # Required no dict
                        if '*' in type_t:
                            key = "*"
                        else:
                            key = [key for key in order.keys() if key in type_t]
                            key = key[0]
                        order[key].append((name , type_t))

                if self.optional_mode in ('boolean', 'define'):
                    # If valid optional_mode, process optional nodes
                    properties = 'optional'
                else:
                    break

            # Recreate a struct sorted by type
            struct.update({struct_n : list()})
            for k,v in order.items():
                tmp_cleaning_list = list()
                for x,y in v:
                    if not x in tmp_cleaning_list:
                        tmp_cleaning_list.append(x)
                        name = x.replace(",","_").replace("-","_")
                        struct[struct_n].append((y,name))
        return struct
