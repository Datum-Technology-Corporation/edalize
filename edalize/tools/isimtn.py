# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause
from io import StringIO
import logging

from edalize.tools.edatool import Edatool
from edalize.utils import EdaCommands

logger = logging.getLogger(__name__)


class Isimtn(Edatool):
    """iSim, True North Silicon's SystemVerilog + VHDL simulator.

    Three commands, three stages: ``isim-vlog`` / ``isim-vcom`` analyse the
    sources into a work library, ``isim-elab`` elaborates the top(s) into a
    native image (``isim_work/a.out.so``), ``isim`` runs the image.

    The tool is named ``isimtn`` because Edalize already has an ``isim``
    backend for the Xilinx ISE Simulator.
    """

    description = "iSim (True North Silicon): SystemVerilog + VHDL simulator, UVM 1.2 built in"

    TOOL_OPTIONS = {
        "isim_vlog_options": {
            "type": "str",
            "desc": "Additional options for isim-vlog (SystemVerilog/Verilog analysis)",
            "list": True,
        },
        "isim_vcom_options": {
            "type": "str",
            "desc": "Additional options for isim-vcom (VHDL analysis)",
            "list": True,
        },
        "isim_elab_options": {
            "type": "str",
            "desc": "Additional options for isim-elab (elaboration)",
            "list": True,
        },
        "isim_run_options": {
            "type": "str",
            "desc": "Additional options for isim at run time, before the plusargs "
            "(e.g. +sv_lib=<a DPI library the core builds itself>)",
            "list": True,
        },
        "timescale": {
            "type": "str",
            "desc": "Default timescale for sources without a `timescale directive, "
            "e.g. 1ns/1ps (-timescale, analysis and elaboration)",
        },
        "uvm": {
            "type": "str",
            "desc": "Map iSim's shipped, pre-compiled UVM of this version into the "
            "work library (-uvm <version>, e.g. 1.2)",
        },
        "dpi_cflags": {
            "type": "str",
            "desc": "Compiler flags for the DPI-C library built from the graph's C/C++ sources",
            "list": True,
        },
        "dpi_ldflags": {
            "type": "str",
            "desc": "Linker flags for that library (e.g. -lutil)",
            "list": True,
        },
    }

    def setup(self, edam):
        super().setup(edam)

        incdirs = []
        vlog_files = []
        vhdl_files = []
        # VHDL by LOGICAL LIBRARY (a file's logical_name; `work` when none),
        # in order of first appearance -- see the legacy backend.
        vhdl_libs = {}
        dpi_sources = []
        dpi_incdirs = []
        sv_libs = []
        unused_files = []
        depfiles = []

        for f in self.files:
            file_type = f.get("file_type", "")
            if file_type.startswith("systemVerilogSource") or file_type.startswith(
                "verilogSource"
            ):
                if not self._add_include_dir(f, incdirs):
                    vlog_files.append(f["name"])
                depfiles.append(f["name"])
            elif file_type.startswith("vhdlSource"):
                vhdl_files.append(f["name"])
                vhdl_libs.setdefault(f.get("logical_name") or "work", []).append(f["name"])
                depfiles.append(f["name"])
            elif file_type in ["cSource", "cppSource"]:
                # A header (is_include_file) is a -I for the DPI compile, not
                # a translation unit.
                if not self._add_include_dir(f, dpi_incdirs):
                    dpi_sources.append(f["name"])
            elif file_type == "dpiLibrary":
                # A run-time input (+sv_lib=), not an analysis dependency.
                sv_libs.append(f["name"])
            else:
                unused_files.append(f)

        self.edam = edam.copy()
        self.edam["files"] = unused_files

        if self.generic:
            # VHDL generic overrides are not wired to isim-elab yet.  Refusing
            # by name beats elaborating a design whose generics the core asked
            # to override and silently did not.
            raise RuntimeError(
                "isimtn: 'generic' parameters are not supported yet: {}. Use "
                "vlogparam for a SystemVerilog top.".format(sorted(self.generic))
            )

        common = []
        timescale = self.tool_options.get("timescale")
        if timescale:
            common += ["-timescale", timescale]
        uvm = self.tool_options.get("uvm")
        if uvm:
            common += ["-uvm", uvm]

        # The analysis command files.  +define+ rides the SystemVerilog one.
        vlog_f = StringIO()
        for incdir in incdirs:
            vlog_f.write("+incdir+{}\n".format(incdir))
        for key, value in self.vlogdefine.items():
            vlog_f.write("+define+{}={}\n".format(key, self._param_value_str(value, "")))
        for name in vlog_files:
            vlog_f.write(name + "\n")
        self.vlog_f = vlog_f.getvalue()
        self.vhdl_fs = {
            "{}.vhdl.{}.f".format(self.name, lib): "".join(name + "\n" for name in names)
            for lib, names in vhdl_libs.items()
        }

        commands = EdaCommands()

        # Analyse.  VHDL first: a SystemVerilog top over VHDL leaves is the
        # common mixed shape, and the work library is shared by both.
        analysed = self.name + ".analysed"
        analyse = []
        config_files = [self.name + ".f"]
        seen_libs = []
        for lib in vhdl_libs:
            cfg = "{}.vhdl.{}.f".format(self.name, lib)
            config_files.append(cfg)
            cmd = ["isim-vcom", "-work", "isim_work", "-lib", lib]
            for l in seen_libs:
                cmd += ["-L", l]
            analyse.append(
                cmd + common + self.tool_options.get("isim_vcom_options", []) + ["-f", cfg]
            )
            seen_libs.append(lib)
        other_libs = [l for l in vhdl_libs if l != "work"]
        if vlog_files:
            analyse.append(
                ["isim-vlog", "-work", "isim_work", "-lib", "work"]
                + common
                + self.tool_options.get("isim_vlog_options", [])
                + ["-f", self.name + ".f"]
            )
        if not analyse:
            raise RuntimeError("isimtn: the target has no HDL source to analyse")
        analyse.append(["touch", analysed])
        commands.add(analyse, [analysed], config_files + depfiles)

        # DPI-C from the graph's C/C++ sources: one shared library, loaded at
        # run time with +sv_lib= (iSim's spelling).
        elab_deps = [analysed]
        if dpi_sources:
            commands.add_var("ISIM_DPI_CC ?= cc")
            commands.add(
                ["$(ISIM_DPI_CC)", "-shared", "-fPIC"]
                + self.tool_options.get("dpi_cflags", [])
                + ["-I" + d for d in dpi_incdirs]
                + ["-o", "isimtn_dpi.so"]
                + dpi_sources
                + self.tool_options.get("dpi_ldflags", []),
                ["isimtn_dpi.so"],
                dpi_sources,
            )
            elab_deps.append("isimtn_dpi.so")
            sv_libs = sv_libs + ["isimtn_dpi.so"]

        # Elaborate.  Several tops are several -top; a vlogparam is a
        # -defparam rooted at each top, the way a written defparam at the
        # design's true top reads.  The argument is single-quoted for the
        # shell the Makefile recipe runs under: a string value is a
        # double-quoted literal to isim-elab, and bare quotes would be eaten.
        tops = self.toplevel.split()
        elab = ["isim-elab", "-work", "isim_work", "-lib", "work"]
        for l in other_libs:
            elab += ["-L", l]
        for top in tops:
            elab += ["-top", top]
        elab += ["-sir"] + common
        for key, value in self.vlogparam.items():
            for top in tops:
                elab += [
                    "-defparam",
                    "'{}.{}={}'".format(top, key, self._param_value_str(value, '"')),
                ]
        elab += self.tool_options.get("isim_elab_options", [])
        image = "isim_work/a.out.so"
        commands.add(elab, [image], elab_deps)
        commands.set_default_target(image)
        self.commands = commands

        # Run, from the work root, where FuseSoC placed the target's copyto:
        # files: $readmemh finds them where the core put them.
        self.run_command = ["isim", "-image", image]
        self.run_command += ["+sv_lib=" + lib for lib in sv_libs]
        self.run_command += self.tool_options.get("isim_run_options", [])
        for key, value in self.plusarg.items():
            self.run_command.append("+{}={}".format(key, self._param_value_str(value)))

    def write_config_files(self):
        self.update_config_file(self.name + ".f", self.vlog_f)
        for cfg, text in self.vhdl_fs.items():
            self.update_config_file(cfg, text)

    def run(self):
        return (self.run_command[0], self.run_command[1:], self.work_root)
