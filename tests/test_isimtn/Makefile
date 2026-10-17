TARGET             := test_isimtn_0
TOPLEVEL           := -top top_module
CONFIG_FILES       := test_isimtn_0.f test_isimtn_0.vhdl.f
ISIM               ?= isim
ISIM_VLOG          ?= isim-vlog
ISIM_VCOM          ?= isim-vcom
ISIM_ELAB          ?= isim-elab
ISIM_DPI_CC        ?= cc
ISIM_COMMON        := -timescale 1ns/1ps -uvm 1.2
ISIM_VLOG_OPTIONS  := some isim_vlog_options
ISIM_VCOM_OPTIONS  := some isim_vcom_options
ISIM_ELAB_OPTIONS  := some isim_elab_options
ISIM_RUN_OPTIONS   := +sv_lib=../../../tb/model.so
ISIM_DEFPARAMS     := -defparam 'top_module.vlogparam_bool=1' -defparam 'top_module.vlogparam_int=42' -defparam 'top_module.vlogparam_str="hello"'
ISIM_SV_LIBS       := +sv_lib=libdpi.so +sv_lib=isimtn_dpi.so
ISIM_DPI_CFLAGS    := -O2
ISIM_DPI_LDFLAGS   := -lutil
DPI_SOURCES        := c_file.c cpp_file.cpp
DPI_INCDIRS        := -I.
DPI_LIB            := isimtn_dpi.so
VCOM_STEP          := $(ISIM_VCOM) -work isim_work -lib work $(ISIM_COMMON) $(ISIM_VCOM_OPTIONS) -f $(TARGET).vhdl.f
VLOG_STEP          := $(ISIM_VLOG) -work isim_work -lib work $(ISIM_COMMON) $(ISIM_VLOG_OPTIONS) -f $(TARGET).f
EXTRA_OPTIONS      ?= +plusarg_bool=1 +plusarg_int=42 +plusarg_str=hello

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
