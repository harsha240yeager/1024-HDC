# Register baseline stream wrapper in Final_HDC after RTL sync (restore full D=1024 core).
# Sourced from rebuild_baseline_integrated.tcl after open_project.

if {![info exists proj_dir]} {
    error "prep_baseline_integrated_project.tcl requires proj_dir"
}

set rtl_rel FInal_HDC.srcs/sources_1/rtl
set wrapper_v_rel [file join $rtl_rel hdc_stream_system_bd_wrapper.v]
set wrapper_sv_rel [file join $rtl_rel hdc_stream_system_bd_wrapper.sv]

set baseline_only {
    pruning_mask.sv
    popcount_am.sv
    hdc_core_top.sv
    hdc_stream_wrapper.sv
    hdc_core_cfg_axi_lite.sv
    encoder_top.sv
    bundle_unit.sv
    item_mem.sv
}

foreach f $baseline_only {
    set rel [file join $rtl_rel $f]
    set abs [file join $proj_dir $rel]
    if {![file exists $abs]} {
        puts "WARNING: missing baseline RTL $abs"
        continue
    }
    set hits [get_files -quiet $rel]
    if {$hits eq ""} {
        add_files -norecurse $rel
        puts "INFO: added $f to project"
    }
}

set old_sv [get_files -quiet $wrapper_sv_rel]
if {$old_sv ne ""} {
    remove_files $old_sv
    puts "INFO: removed SystemVerilog BD wrapper from project (module_ref requires .v top)"
}

if {[file exists [file join $proj_dir $wrapper_v_rel]]} {
    set hits [get_files -quiet $wrapper_v_rel]
    if {$hits eq ""} {
        add_files -norecurse $wrapper_v_rel
        puts "INFO: added baseline hdc_stream_system_bd_wrapper.v to project"
    }
}

update_compile_order -force
