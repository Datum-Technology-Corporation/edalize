import pytest

from .edalize_tool_common import tool_fixture


def test_tool_isimtn(tool_fixture):
    tool_options = {
        "timescale": "1ns/1ps",
        "uvm": "1.2",
        "isim_vlog_options": ["some", "isim_vlog_options"],
        "isim_vcom_options": ["some", "isim_vcom_options"],
        "isim_elab_options": ["some", "isim_elab_options"],
        "isim_run_options": ["+sv_lib=../../../tb/model.so"],
        "dpi_cflags": ["-O2"],
        "dpi_ldflags": ["-lutil"],
    }
    tf = tool_fixture("isimtn", tool_options=tool_options)

    tf.tool.configure()
    tf.compare_config_files(["design.f", "design.vhdl.work.f", "design.vhdl.libx.f"])
    tf.compare_makefile()

    # The run is handed back to the flow: the image, the DPI libraries, the
    # run options, then the plusargs -- from the work root.
    (cmd, args, cwd) = tf.tool.run()
    assert cmd == "isim"
    assert args == [
        "-image",
        "isim_work/a.out.so",
        "+sv_lib=libdpi.so",
        "+sv_lib=isimtn_dpi.so",
        "+sv_lib=../../../tb/model.so",
        "+plusarg_bool=1",
        "+plusarg_int=42",
        "+plusarg_str=hello",
    ]
    assert cwd == tf.tool.work_root


def test_tool_isimtn_multiple_tops(tool_fixture):
    tf = tool_fixture("isimtn", toplevel="top1 top2", ref_subdir="multitop")

    tf.tool.configure()
    tf.compare_makefile()


def test_tool_isimtn_generic_refused(tool_fixture):
    """VHDL generic overrides are not wired yet: refused by name, never dropped."""
    with pytest.raises(RuntimeError, match="'generic' parameters are not supported"):
        tool_fixture("isimtn", paramtypes=["generic"])
