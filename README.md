________________________________________________________________________________
# Introduction:
This fork of lopper intends to generate C struct and data from a devicetree.
The goal is to generate these for baremetal components (e.g. TF-M, some RToS or internal).

The assist dt_to_c.py used in alongside [py-dtbindings](https://github.com/ValentinGrim/py-dtbindings)
and baremetal/board_header.py will try to do that.

There is some work in progress and quick-and-dirty stuff going on here but, it ~work.

## git:
  This fork uses submodules 

    git clone --recurse-submodules https://github.com/ValentinGrim/lopper
    sudo apt install swig python3 python3-ruamel.yaml
    pip3 install -r ./py-dtbindings/requirement.txt

# Workflow:
Calling :

    ./lopper.py -f --werror -i ./lopper/lops/lop-dt-to-c.dts my_input_devicetree.dts

Will result the following
- After lopper done his job, dt_to_c assist will be called
  - Init a mySDTBindings which is the main class of [py-dtbindings](https://github.com/ValentinGrim/py-dtbindings) (used to access dt-bindings and dt-schemas info)

  - Init a myBoardHeader which is the main class of baremetal/board_header.py (used to write the final files)

  - Init a "clean node list" which will contain all "okay" nodes from the devicetree.

  - A loop will call struct_generator and platdata_generator on all nodes from the clean node list in order to generate C struct definition and declarations for each node.

- Generation:
  - struct_generator will use [py-dtbindings](https://github.com/ValentinGrim/py-dtbindings)
  to extract the required list from dt-bindings (actually cloned from [kernel.org](https://www.kernel.org/doc/Documentation/devicetree/bindings/))

  - With this required list, it will also have type information that [py-dtbindings](https://github.com/ValentinGrim/py-dtbindings)
  will extract from [dt-schema](https://github.com/devicetree-org/dt-schema)

  - Having all this information will allow struct_generator to generate a C struct
  definition.

  - platdata_generator will then generate a C struct declaration named _nodename_address_ using devicetree values.

  - [WIP] Properties that contain phandle will be processed as a pointer and we will
  try to generate struct and platdata for these calling the same struct_generator and
  platdata_generator

- Ending:
  - All the generated data has been given to the myBoardHeader class which will
  write down all of these in a combo board_header.c / .h located in build dir
  (path can be changed as it is an arg of the class constructor)

  - Warning ! Some values and struct won't be that clean and may not compile.
  Especially if there is phandle in them.

# Suggestion / Remarks / Comments ?
Feel free to contact me @ vmonnot@outlook.com
________________________________________________________________________________
# Overview:

Fundamentally, lopper takes an input device tree (normally a system device tree),
applies operations to that tree, and outputs one or more modified/processed trees.

See the README-architecture.txt for details on how lopper works. This README file
has practical information, known limitations and TODO items.

# config/setup:

Lopper is in a single repository, and is available via git or pypi:

### git:

   % git clone git://github.com/devicetree-org/lopper

   Ensure that the prerequisite tools are installed on your host. Lopper is written
   in python3, and requires that standard support libraries are installed. Current
   testing has been against python3.5.x, but no issues are expected on newer 3.x
   releases.

   In addition to the standard libraries, Lopper uses: pcpp (or cpp), humanfriendly,
   dtc and libfdt for processing and manipulating device trees. These tools must be
   installed and on the PATH.

   **Note:** (python cpp) pcpp is optional (available on PyPi), and if not available cpp
   will be used for pre-processing input files. If comments are to be maintained
   through the processing flow, pcpp must be used since it has functionality to
   not strip them during processing.

   For yaml file processing, lopper has an optional dependency on python's yaml
   and ruamel as well as anytree for importing the contents of yaml files.

### pypi:

   % pip install lopper

   The pip installation will pull in the required dependencies, and also contains
   the following optional features:

      - 'server' : enable if the ReST API server is required
      - 'yaml'   : enable for yaml support
      - 'dt'     : enable if non-libfdt support is required
      - 'pcpp'   : enable for enhanced preprocessing functionality

   i.e.:

   % pip install lopper[server,yaml,dt,pcpp]

   **Note:** lopper (via clone or pip) contains a vendored python libfdt (from dtc), since
   it is not available via a pip dependency. If the vendored versions do not match
   the python in use, you must manually ensure that libfdt is installed and
   available.

   If it is not in a standard location, make sure it is on PYTHONPATH:

   % export PYTHONPATH=<path to pylibfdt>:$PYTHONPATH

# submitting patches / reporting issues

Pull requests or patches are acceptable for sending changes/fixes/features to Lopper,
chose whichever matches your preferred workflow.

For pull requests and issues:

  - Use the Lopoper github: https://github.com/devicetree-org/lopper

For Patches:

  - Use the groups.io mailing list: https://groups.io/g/lopper-devel
  - kernel (lkml) style patch sending is preferred
  - Send patches via git send-mail, using something like:

     % git send-email -M --to lopper-devel@groups.io <path to your patches>

For discussion:

  - Use the mailing list or the github wiki/dicussions/issue tracker

# Lopper overview:

lopper.py --help

    Usage: lopper.py [OPTION] <system device tree> [<output file>]...
      -v, --verbose       enable verbose/debug processing (specify more than once for more verbosity)
      -t, --target        indicate the starting domain for processing (i.e. chosen node or domain label)
        , --dryrun        run all processing, but don't write any output files
      -d, --dump          dump a dtb as dts source
      -i, --input         process supplied input device tree description
      -a, --assist        load specified python assist (for node or output processing)
      -A, --assist-paths  colon separated lists of paths to search for assist loading
        , --enhanced      when writing output files, do enhanced processing (this includes phandle replacement, comments, etc
        . --auto          automatically run any assists passed via -a
        , --permissive    do not enforce fully validated properties (phandles, etc)
      -o, --output        output file
        , --overlay       Allow input files (dts or yaml) to overlay system device tree nodes
      -x. --xlate         run automatic translations on nodes for indicated input types (yaml,dts)
        , --no-libfdt     don't use dtc/libfdt for parsing/compiling device trees
      -f, --force         force overwrite output file(s)
        , --werror        treat warnings as errors
      -S, --save-temps    don't remove temporary files
        , --cfgfile       specify a lopper configuration file to use (configparser format)
        , --cfgval        specify a configuration value to use (in configparser section format). Can be specified multiple times
      -h, --help          display this help and exit
      -O, --outdir        directory to use for output files
        , --server        after processing, start a server for ReST API calls
        , --version       output the version and exit

A few command line notes:

 -i <file>: these can be either lop files, or device tree files (system device
            tree or other). The compatible string in lop files is used to
            distinguish operation files from device tree files. If passed, multiple
            device tree files are concatenated before processing.

 <output> file: The default output file for the modified system device tree. lopper
                operations can output more variants as required

**Note:** Since lopper manipulates dtb's (as compiled by dtc), some information
that is in the source dts is lost on the output of the final dts. This includes
comments, symbolic phandles, formatting of strings, etc. If you are transforming
to dts files and want to maintain this information, use the --enhanced flag.
This flag indicates that lopper should perform pre-processing and output phandle
mapping to restore both comments, labels and symbolic phandles to the final
output.

**Note:** By default Lopper puts pre-processed files (.pp) into the same
directory as the system device tree. This is required, since in some cases when
the .pp files and device tree are not in the same directory, dtc cannot resolve
labels from include files, and will error. That being said, if the -O option is
used to specify an output directory, the pre-processed file will be placed
there. If we get into a mode where the system device tree's directory is not
writeable, or the -O option is breaking symbol resolution, then we'll have to
either copy everything to the output directory, or look into why dtc can't
handle the split directories and include files.

## Sample run:

  % ./lopper.py -f --enhanced --werror -v -v -i lopper/lops/lop-load.dts -i lopper/lops/lop-domain-r5.dts device-trees/system-device-tree.dts modified-sdt.dts


  % python -m lopper -f --enhanced --werror -v -v -i lopper/lops/lop-load.dts -i lopper/lops/lop-domain-r5.dts device-trees/system-device-tree.dts modified-sdt.dts

## Limitations:

 - Internal interfaces are subject to change
