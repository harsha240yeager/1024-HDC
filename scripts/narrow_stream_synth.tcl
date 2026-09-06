# Stream-wrapper OOC synth only (core reports already present)
set part   "xc7z020clg484-1"
set period 10.0
if {$argc >= 1} { set part   [lindex $argv 0] }
if {$argc >= 2} { set period [lindex $argv 1] }

set repo   [file normalize [file join [file dirname [info script]] ..]]
set outdir [file join $repo results dsweep]
file mkdir $outdir

set vecdir [file join $repo python_ref vectors cosim_core]
set ch_mem [file join $vecdir item_mem_channel.mem]
set ft_mem [file join $vecdir item_mem_feature.mem]
set val_mem [file join $vecdir item_mem_value.mem]

proc run_ooc {top rtl_files rpt_name} {
    global repo part period outdir ch_mem ft_mem val_mem

    puts "==== OOC synth: $top -> $rpt_name =============================="
    create_project -in_memory -part $part
    foreach f $rtl_files {
        read_verilog -sv [file join $repo $f]
    }
    synth_design -top $top -mode out_of_context \
        -generic CH_MEM=$ch_mem \
        -generic FT_MEM=$ft_mem \
        -generic VAL_MEM=$val_mem

    if {[llength [get_ports -quiet clk]] > 0} {
        create_clock -name clk -period $period [get_ports clk]
    } elseif {[llength [get_ports -quiet aclk]] > 0} {
        create_clock -name aclk -period $period [get_ports aclk]
    }

    set rpt [file join $outdir $rpt_name]
    report_utilization -file $rpt
    report_utilization -hierarchical -file $rpt -append
    report_timing_summary -file $rpt -append
    close_project
}

set baseline_stream_rtl {
    rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv rtl/pruning_mask.sv
    rtl/popcount_am.sv rtl/hdc_core_top.sv rtl/hdc_stream_wrapper.sv
}
set narrow_stream_rtl {
    rtl/hdc_sel_pkg.sv rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv
    rtl/popcount_am_narrow.sv rtl/hdc_core_top_narrow.sv rtl/hdc_stream_wrapper_narrow.sv
}

run_ooc hdc_stream_wrapper $baseline_stream_rtl synth_baseline_stream.txt
run_ooc hdc_stream_wrapper_narrow $narrow_stream_rtl synth_narrow_stream.txt
puts "Stream OOC synth complete."
