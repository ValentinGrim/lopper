#/*
#* Author:
#*       Valentin Monnot <vmonnot@outlook.com>
#*
#* SPDX-License-Identifier: BSD-3-Clause
#*/

import sys

class BoardHeader:
    def __init__(self, path):
        """
        This class intend to be used to as a writter.

            Parameters:
                path (str): The path where output files should be generated.

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

        self._header.write("""/*
 * This file has been automatically generated using lopper
 * @script        dt_to_c.py
 */

#ifndef __BOARD_HEADER_H__
#define __BOARD_HEADER_H__

#include <stdint.h>
#include <stddef.h>
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
            return self._struct[name].copy()
        return None

    def add2struct(self, struct):
        """
        Setter for internal _struct
        """
        if not list(struct.keys())[0] in self._struct.keys():
            self._struct.update(struct)

    def struct_keys():
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

        self._header.write('\n#endif // __BOARD_HEADER_H__')
        self._header.close()

        # Source
        self._source.write('\n')
        for struct_n, struct_v in sorted(self._struct.items()):
            self._source.write("struct %s_s{\n" % struct_n.replace("-","_"))
            for name, type_t in struct_v['required'].items():
                if type(type_t) == dict:
                    for k,v in type_t.items():
                        self._source.write("    const %s %s;\n" % (v,k.replace(",","_").replace("-","_")))
                else:
                    self._source.write("    const %s %s;\n" % (type_t,name.replace(",","_").replace("-","_")))
            self._source.write("};\n")

        self._source.write('\n')

        for generated in sorted(self._generated):
            self._source.write(generated)

        self._source.write('\n')

        for const_n, const_v in self._const.items():
            type_t = const_v["type"].replace("-","_")
            self._source.write("const %s %s = {\n" % (type_t,const_n.replace("-","_")))
            for name, value in const_v['required'].items():
                if type(value) == dict:
                    for k,v in value.items():
                        self._source.write("    .%s = %s,\n" % (k,v))
                else:
                    self._source.write("    .%s = %s,\n" % (name.replace(',','_').replace('-','_'), value))
            self._source.write("};\n")

        self._source.close()
