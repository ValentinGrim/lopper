#/*
#* Author:
#*       Valentin Monnot <vmonnot@outlook.com>
#*
#* SPDX-License-Identifier: BSD-3-Clause
#*/

import sys

class BoardHeader:
    def __init__(self, path):
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
 * @script        tfm_config.py
 */

#ifndef __BOARD_HEADER_H__
#define __BOARD_HEADER_H__

#include <stdint.h>
#include <stddef.h>
""")
        self._source.write("""/*
 * This file has been automatically generated using lopper
 * @script        tfm_config.py
 */

#include "board_header.h"
""")

    ##
    #    @fn            __getitem__(self, name)
    #    @brief        Magic method that return an item from #_struct if exist
    def __getitem__(self, name):
        if name in self._struct.keys():
            return self._struct[name]
        return None

    def add2struct(self, struct):
        if not list(struct.keys())[0] in self._struct.keys():
            self._struct.update(struct)

    def add2typedef(self, typedef):
        if not typedef in self._typedef:
            self._typedef.append(typedef)

    def add2extern(self, extern):
        if not extern in self._extern:
            self._extern.append(extern)

    def add2generated(self, generated):
        if not generated in self._generated:
            self._generated.append(generated)

    def add2const(self, const, name):
        if not name in self._struct.keys():
            self._const.update({name : const})

    def update_type(self, name, key, type_t):
        self._struct[name][key] = type_t

    def close(self):
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
            for name, type_t in struct_v.items():
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
            for name, value in const_v['values'].items():
                self._source.write("    .%s = %s,\n" % (name, value))
            self._source.write("};\n")

        self._source.close()
