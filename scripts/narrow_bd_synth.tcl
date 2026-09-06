# OOC synth: stream system bd wrappers (integrated PL IP level, no PS/DMA)
set part "xc7z020clg484-1"
set period 10.0
set repo [file normalize [file join [file dirname [info script]] ..]]
set outdir [file join $repo results dsweep]
file mkdir $outdir

set vecdir [file join $repo python_ref vectors cosim_core]]

proc run_bd_ooc {top rtl_files rpt_name ch_mem ft_mem val_mem} {
    global repo part period outdir
    puts "==== OOC synth: $top -> $rpt_name =============================="
    create_project -in_memory -part $part
    foreach f $rtl_files { read_verilog -sv [file join $repo $f] }
    synth_design -top $top -mode out_of_context \
        -generic CH_MEM=$ch_mem \
        -generic FT_MEM=$ft_mem \
        -generic VAL_MEM=$val_mem
    create_clock -name aclk -period $period [get_ports aclk]
    set rpt [file join $outdir $rpt_name]
    report_utilization -file $rpt
    report_utilization -hierarchical -file $rpt -append
    report_timing_summary -file $rpt -append
    close_project
}

set ch_mem [file join $vecdir item_mem_channel.mem]
set ft_mem [file join $vecdir item_mem_feature.mem]
set val_mem [file join $vecdir item_mem_value.mem]

set baseline_bd {
    rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv rtl/pruning_mask.sv
    rtl/popcount_am.sv rtl/hdc_core_top.sv rtl/hdc_stream_wrapper.sv
    rtl/hdc_core_cfg_axi_lite.sv rtl/hdc_stream_system_bd_wrapper.sv
}
set narrow_bd {
    rtl/hdc_sel_pkg.sv rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv
    rtl/popcount_am_narrow.sv rtl/hdc_core_top_narrow.sv rtl/hdc_stream_wrapper_narrow.sv
    rtl/hdc_core_cfg_axi_lite_narrow.sv rtl/hdc_stream_system_bd_wrapper_narrow.sv
}

run_bd_ooc hdc_stream_system_bd_wrapper $baseline_bd synth_baseline_bd.txt $ch_mem $ft_mem $val_mem
run_bd_ooc hdc_stream_system_bd_wrapper_narrow $narrow_bd synth_narrow_bd.txt $ch_mem $ft_mem $val_mem
puts "BD-wrapper OOC synth complete."
