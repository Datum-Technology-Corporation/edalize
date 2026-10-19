import pytest

from .edalize_common import make_edalize_test


def test_isimtn(make_edalize_test, monkeypatch):
    name = "test_isimtn_0"
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
    tf = make_edalize_test("isimtn", test_name=name, tool_options=tool_options)

    tf.backend.configure()
    tf.compare_files(["Makefile", name + ".f", name + ".vhdl.work.f", name + ".vhdl.libx.f"])

    # The DPI library is linked with the compiler the Makefile names; the
    # mock records its arguments like every other mocked tool.
    monkeypatch.setenv("ISIM_DPI_CC", "isim-dpi-cc")
    tf.backend.build()
    tf.compare_files(["isim-vcom.cmd", "isim-vlog.cmd", "isim-dpi-cc.cmd", "isim-elab.cmd"])

    tf.backend.run()
    tf.compare_files(["isim.cmd"])


def test_isimtn_minimal(tmpdir):
    """A target with no HDL source is refused, not built empty."""
    from edalize.edatool import get_edatool

    edam = {"name": "test_isimtn_minimal_0", "toplevel": "top"}
    backend = get_edatool("isimtn")(edam=edam, work_root=str(tmpdir))
    with pytest.raises(RuntimeError, match="no HDL source"):
        backend.configure()
