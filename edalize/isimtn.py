# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause
#
# iSim, True North Silicon's SystemVerilog + VHDL simulator -- the legacy
# (`fusesoc --tool=isimtn`) backend.  The flow-API tool is edalize/tools/isimtn.py.
# Named "isimtn" because Edalize already has an "isim" backend, for the Xilinx
# ISE Simulator.
import os
import logging

from edalize.edatool import Edatool

logger = logging.getLogger(__name__)

MAKEFILE_TEMPLATE = """
all: $(TARGET).elab

$(TARGET).analysed: $(CONFIG_FILES)
	$(VCOM_STEP)
	$(VLOG_STEP)
	touch $@

$(TARGET).elab: $(TARGET).analysed $(DPI_LIB)
	$(ISIM_ELAB) -work isim_work -lib work $(TOPLEVEL) -sir $(ISIM_COMMON) $(ISIM_DEFPARAMS) $(ISIM_ELAB_OPTIONS)
	touch $@

isimtn_dpi.so: $(DPI_SOURCES)
	$(ISIM_DPI_CC) -shared -fPIC $(ISIM_DPI_CFLAGS) $(DPI_INCDIRS) -o $@ $(DPI_SOURCES) $(ISIM_DPI_LDFLAGS)

run: $(TARGET).elab
	$(ISIM) -image isim_work/a.out.so $(ISIM_SV_LIBS) $(ISIM_RUN_OPTIONS) $(EXTRA_OPTIONS)

clean:
	$(RM) -r isim_work $(TARGET).analysed $(TARGET).elab isimtn_dpi.so
"""


class Isimtn(Edatool):

    argtypes = ["plusarg", "vlogdefine", "vlogparam"]

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {
                "description": "iSim (True North Silicon): SystemVerilog + VHDL simulator, UVM 1.2 built in. Analyse with isim-vlog/isim-vcom, elaborate with isim-elab, run with isim.",
                "members": [
                    {
                        "name": "timescale",
                        "type": "String",
                        "desc": "Default timescale for sources without a `timescale directive, e.g. 1ns/1ps",
                    },
                    {
                        "name": "uvm",
                        "type": "String",
                        "desc": "Map iSim's shipped, pre-compiled UVM of this version into the work library (e.g. 1.2)",
                    },
                ],
                "lists": [
                    {
                        "name": "isim_vlog_options",
                        "type": "String",
                        "desc": "Additional options for isim-vlog",
                    },
                    {
                        "name": "isim_vcom_options",
                        "type": "String",
                        "desc": "Additional options for isim-vcom",
                    },
                    {
                        "name": "isim_elab_options",
                        "type": "String",
                        "desc": "Additional options for isim-elab",
                    },
                    {
                        "name": "isim_run_options",
                        "type": "String",
                        "desc": "Additional options for isim at run time, before the plusargs (e.g. +sv_lib=<library>)",
                    },
                    {
                        "name": "dpi_cflags",
                        "type": "String",
                        "desc": "Compiler flags for the DPI-C library built from the graph's C/C++ sources",
                    },
                    {
                        "name": "dpi_ldflags",
                        "type": "String",
                        "desc": "Linker flags for that library (e.g. -lutil)",
                    },
                ],
            }

    def configure_main(self):
        logger.warning(
            "This backend is deprecated and will eventually be removed. Please migrate to the flow API instead.  See https://edalize.readthedocs.io/en/latest/ref/migrations.html#migrating-from-tool-backends-to-flows for more details."
        )
        (src_files, incdirs) = self._get_fileset_files()

        vlog_files = []
        vhdl_files = []
        dpi_sources = []
        sv_libs = []
        for f in src_files:
            if f.file_type.startswith("systemVerilogSource") or f.file_type.startswith(
                "verilogSource"
            ):
                vlog_files.append(f.name)
            elif f.file_type.startswith("vhdlSource"):
                vhdl_files.append(f.name)
            elif f.file_type in ["cSource", "cppSource"]:
                dpi_sources.append(f.name)
            elif f.file_type == "dpiLibrary":
                sv_libs.append(f.name)
            elif f.file_type == "user":
                pass
            else:
                logger.warning("{} has unknown file type '{}'".format(f.name, f.file_type))
        if not vlog_files and not vhdl_files:
            raise RuntimeError("isimtn: the target has no HDL source to analyse")

        with open(os.path.join(self.work_root, self.name + ".f"), "w") as f:
            for incdir in incdirs:
                f.write("+incdir+" + incdir + "\n")
            for key, value in self.vlogdefine.items():
                f.write("+define+{}={}\n".format(key, self._param_value_str(value, "")))
            for name in vlog_files:
                f.write(name + "\n")
        config_files = [self.name + ".f"]
        if vhdl_files:
            with open(os.path.join(self.work_root, self.name + ".vhdl.f"), "w") as f:
                for name in vhdl_files:
                    f.write(name + "\n")
            config_files.append(self.name + ".vhdl.f")

        common = []
        timescale = self.tool_options.get("timescale")
        if timescale:
            common += ["-timescale", timescale]
        uvm = self.tool_options.get("uvm")
        if uvm:
            common += ["-uvm", uvm]

        # Single-quoted for the shell the Makefile recipe runs under: a string
        # value is a double-quoted literal to isim-elab.
        tops = self.toplevel.split()
        defparams = []
        for key, value in self.vlogparam.items():
            for top in tops:
                defparams.append(
                    "-defparam '{}.{}={}'".format(top, key, self._param_value_str(value, '"'))
                )
        if dpi_sources:
            sv_libs = sv_libs + ["isimtn_dpi.so"]

        def opts(key):
            return " ".join(self.tool_options.get(key, []))

        with open(os.path.join(self.work_root, "Makefile"), "w") as f:
            f.write("TARGET             := {}\n".format(self.name))
            f.write("TOPLEVEL           := {}\n".format(" ".join("-top " + t for t in tops)))
            f.write("CONFIG_FILES       := {}\n".format(" ".join(config_files)))
            f.write("ISIM               ?= isim\n")
            f.write("ISIM_VLOG          ?= isim-vlog\n")
            f.write("ISIM_VCOM          ?= isim-vcom\n")
            f.write("ISIM_ELAB          ?= isim-elab\n")
            f.write("ISIM_DPI_CC        ?= cc\n")
            f.write("ISIM_COMMON        := {}\n".format(" ".join(common)))
            f.write("ISIM_VLOG_OPTIONS  := {}\n".format(opts("isim_vlog_options")))
            f.write("ISIM_VCOM_OPTIONS  := {}\n".format(opts("isim_vcom_options")))
            f.write("ISIM_ELAB_OPTIONS  := {}\n".format(opts("isim_elab_options")))
            f.write("ISIM_RUN_OPTIONS   := {}\n".format(opts("isim_run_options")))
            f.write("ISIM_DEFPARAMS     := {}\n".format(" ".join(defparams)))
            f.write("ISIM_SV_LIBS       := {}\n".format(" ".join("+sv_lib=" + lib for lib in sv_libs)))
            f.write("ISIM_DPI_CFLAGS    := {}\n".format(opts("dpi_cflags")))
            f.write("ISIM_DPI_LDFLAGS   := {}\n".format(opts("dpi_ldflags")))
            f.write("DPI_SOURCES        := {}\n".format(" ".join(dpi_sources)))
            f.write("DPI_INCDIRS        := {}\n".format(" ".join("-I" + d for d in incdirs) if dpi_sources else ""))
            f.write("DPI_LIB            := {}\n".format("isimtn_dpi.so" if dpi_sources else ""))
            f.write(
                "VCOM_STEP          := {}\n".format(
                    "$(ISIM_VCOM) -work isim_work -lib work $(ISIM_COMMON) $(ISIM_VCOM_OPTIONS) -f $(TARGET).vhdl.f"
                    if vhdl_files
                    else "true"
                )
            )
            f.write(
                "VLOG_STEP          := {}\n".format(
                    "$(ISIM_VLOG) -work isim_work -lib work $(ISIM_COMMON) $(ISIM_VLOG_OPTIONS) -f $(TARGET).f"
                    if vlog_files
                    else "true"
                )
            )
            if self.plusarg:
                plusargs = []
                for key, value in self.plusarg.items():
                    plusargs += ["+{}={}".format(key, self._param_value_str(value))]
                f.write("EXTRA_OPTIONS      ?= {}\n".format(" ".join(plusargs)))
            f.write(MAKEFILE_TEMPLATE)

    def run_main(self):
        args = ["run"]
        if self.plusarg:
            plusargs = []
            for key, value in self.plusarg.items():
                plusargs += ["+{}={}".format(key, self._param_value_str(value))]
            args.append("EXTRA_OPTIONS=" + " ".join(plusargs))
        self._run_tool("make", args)
