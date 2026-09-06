# ===========================================================================
# narrow_vs_baseline_synth.tcl -- OOC synthesis: baseline vs narrow (issue #29)
#
# Compares hdc_core_top (baseline, D=1024 + pruning_mask) against
# hdc_core_top_narrow (K=128 anchor C) and the stream wrappers, recording
# flat + hierarchical utilisation and post-synth timing.
#
# Run from repo root (Vivado on PATH):
#   vivado -mode batch -source scripts/narrow_vs_baseline_synth.tcl
#
# Optional -tclargs:
#   arg0 = part           (default xc7z020clg484-1)
#   arg1 = clock period ns (default 10.0 => 100 MHz)
#
# Outputs under results/dsweep/:
#   synth_baseline_core.txt, synth_narrow_core.txt
#   synth_baseline_stream.txt, synth_narrow_stream.txt
#   narrow_vs_baseline_util.csv  (via compare script)
# ===========================================================================

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

if {![file exists $ch_mem]} {
    puts "Regenerating D=1024 item_mem ROMs ..."
    exec python3 [file join $repo python_ref generate_vectors.py] \
        --core --D 1024 --count 50 --seed 42 \
        --out-dir [file join $repo python_ref vectors cosim_core]
}

proc scrape_slice_row {rpt label} {
    set fh [open $rpt r]
    set txt [read $fh]
    close $fh
    set pat [format {^\|\s*%s\s*\|\s*([0-9]+)\s*\|} $label]
    if {[regexp -line $pat $txt -> val]} {
        return $val
    }
    return "n/a"
}

proc scrape_wns {rpt} {
    set fh [open $rpt r]
    set txt [read $fh]
    close $fh
    if {[regexp {WNS\(ns\)\s*\|\s*([-0-9.]+)} $txt -> wns]} {
        return $wns
    }
    set paths [get_timing_paths -delay_type max -nworst 1]
    if {[llength $paths] == 0} { return "n/a" }
    set wns [get_property SLACK [lindex $paths 0]]
    if {$wns eq "" || $wns eq "inf"} { return "n/a" }
    return $wns
}

proc run_ooc {top rtl_files rpt_name} {
    global repo part period outdir ch_mem ft_mem val_mem

    puts "==== OOC synth: $top -> $rpt_name =============================="
    create_project -in_memory -part $part
    foreach f $rtl_files {
        read_verilog -sv [file join $repo $f]
    }

    if {$top eq "hdc_core_top"} {
        synth_design -top $top -mode out_of_context \
            -generic CH_MEM=$ch_mem \
            -generic FT_MEM=$ft_mem \
            -generic VAL_MEM=$val_mem
    } elseif {$top eq "hdc_core_top_narrow"} {
        synth_design -top $top -mode out_of_context \
            -generic CH_MEM=$ch_mem \
            -generic FT_MEM=$ft_mem \
            -generic VAL_MEM=$val_mem
    } elseif {$top eq "hdc_stream_wrapper"} {
        synth_design -top $top -mode out_of_context \
            -generic CH_MEM=$ch_mem \
            -generic FT_MEM=$ft_mem \
            -generic VAL_MEM=$val_mem
    } elseif {$top eq "hdc_stream_wrapper_narrow"} {
        synth_design -top $top -mode out_of_context \
            -generic CH_MEM=$ch_mem \
            -generic FT_MEM=$ft_mem \
            -generic VAL_MEM=$val_mem
    } else {
        synth_design -top $top -mode out_of_context
    }

    if {[llength [get_ports -quiet clk]] > 0} {
        create_clock -name clk -period $period [get_ports clk]
    } elseif {[llength [get_ports -quiet aclk]] > 0} {
        create_clock -name aclk -period $period [get_ports aclk]
    }

    set rpt [file join $outdir $rpt_name]
    report_utilization -file $rpt
    report_utilization -hierarchical -file $rpt -append
    report_timing_summary -file $rpt -append

    set luts [scrape_slice_row $rpt "Slice LUTs\\*"]
    set ffs  [scrape_slice_row $rpt "Slice Registers"]
    set wns  [scrape_wns $rpt]
    set fmax "n/a"
    if {$wns ne "n/a"} {
        set fmax [format "%.1f" [expr {1000.0 / ($::period - $wns)}]]
    }

    close_project
    return [list $luts $ffs $wns $fmax]
}

set baseline_core_rtl {
    rtl/item_mem.sv
    rtl/bundle_unit.sv
    rtl/encoder_top.sv
    rtl/pruning_mask.sv
    rtl/popcount_am.sv
    rtl/hdc_core_top.sv
}

set narrow_core_rtl {
    rtl/hdc_sel_pkg.sv
    rtl/item_mem.sv
    rtl/bundle_unit.sv
    rtl/encoder_top.sv
    rtl/popcount_am_narrow.sv
    rtl/hdc_core_top_narrow.sv
}

set baseline_stream_rtl [concat $baseline_core_rtl {rtl/hdc_stream_wrapper.sv}]
set narrow_stream_rtl [concat $narrow_core_rtl {rtl/hdc_stream_wrapper_narrow.sv}]

set csv [open [file join $outdir narrow_vs_baseline_util.csv] w]
puts $csv "variant,top,k_bits,scope,lut,ff,wns_ns,fmax_mhz,report"

if {![file exists [file join $outdir synth_baseline_core.txt]]} {
    puts $csv "baseline,hdc_core_top,1024,ooc_core,[join [run_ooc hdc_core_top $baseline_core_rtl synth_baseline_core.txt] ,],synth_baseline_core.txt"
} else {
    puts "SKIP: synth_baseline_core.txt exists"
}
if {![file exists [file join $outdir synth_narrow_core.txt]]} {
    puts $csv "narrow,hdc_core_top_narrow,128,ooc_core,[join [run_ooc hdc_core_top_narrow $narrow_core_rtl synth_narrow_core.txt] ,],synth_narrow_core.txt"
} else {
    puts "SKIP: synth_narrow_core.txt exists"
}
flush $csv
puts $csv "baseline,hdc_stream_wrapper,1024,ooc_stream,[join [run_ooc hdc_stream_wrapper $baseline_stream_rtl synth_baseline_stream.txt] ,],synth_baseline_stream.txt"
flush $csv
puts $csv "narrow,hdc_stream_wrapper_narrow,128,ooc_stream,[join [run_ooc hdc_stream_wrapper_narrow $narrow_stream_rtl synth_narrow_stream.txt] ,],synth_narrow_stream.txt"
close $csv

puts "Done. Reports in $outdir — run scripts/compare_narrow_vs_baseline_lut.sh for CSV."
