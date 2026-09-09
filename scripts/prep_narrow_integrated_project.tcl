# Register narrow RTL in the Vivado project after RTL sync (issue #29 integrated).
# Sourced from rebuild_narrow_integrated.tcl after open_project.
#
# Vivado mishandles absolute paths when the project directory contains spaces
# (e.g. ".../Final HDC/FInal_HDC"). Use paths relative to $proj_dir.

if {![info exists proj_dir]} {
    error "prep_narrow_integrated_project.tcl requires proj_dir"
}

set rtl_rel FInal_HDC.srcs/sources_1/rtl

set narrow_only {
    hdc_sel_pkg.sv
    popcount_am_narrow.sv
    hdc_core_top_narrow.sv
    hdc_stream_wrapper_narrow.sv
    hdc_core_cfg_axi_lite_narrow.sv
}

foreach f $narrow_only {
    set rel [file join $rtl_rel $f]
    set abs [file join $proj_dir $rel]
    if {![file exists $abs]} {
        puts "WARNING: missing narrow RTL $abs"
        continue
    }
    set hits [get_files -quiet $rel]
    if {$hits eq ""} {
        add_files -norecurse $rel
        puts "INFO: added $f to project"
    }
}

set wrapper_v_rel [file join $rtl_rel hdc_stream_system_bd_wrapper.v]
set wrapper_sv_rel [file join $rtl_rel hdc_stream_system_bd_wrapper.sv]

set old_sv [get_files -quiet $wrapper_sv_rel]
if {$old_sv ne ""} {
    remove_files $old_sv
    puts "INFO: removed SystemVerilog BD wrapper from project (module_ref requires .v top)"
}

if {[file exists [file join $proj_dir $wrapper_v_rel]]} {
    set hits [get_files -quiet $wrapper_v_rel]
    if {$hits eq ""} {
        add_files -norecurse $wrapper_v_rel
        puts "INFO: added hdc_stream_system_bd_wrapper.v to project"
    }
}

update_compile_order -force
