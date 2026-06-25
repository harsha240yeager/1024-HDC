# ===========================================================================
# dsweep_synth.tcl -- Out-of-context D-sweep synthesis of hdc_core_top.
#
# Closes the June gap "D parameterization not synthesis-verified": builds the
# core at D in {256, 512, 1024, 2048} (WORDS = D/64) and records LUT / FF /
# slice utilisation + timing (WNS / Fmax) for the Hook A Pareto D-axis.
#
# This is an OOC (module-level) synthesis run -- it characterises the HDC core
# itself, independent of the Zynq PS / DMA wrapper, which is what the Pareto
# D-axis needs.  It does NOT place&route a full bitstream (that stays in the
# FInal_HDC Vivado project); it gives utilisation + post-synth timing per D.
#
# Run (Vivado must be on PATH; run from the repo root):
#     vivado -mode batch -source scripts/dsweep_synth.tcl
#
# Override the device / clock / D-list with -tclargs:
#     vivado -mode batch -source scripts/dsweep_synth.tcl \
#            -tclargs xc7z020clg484-1 10.0 "256 512 1024 2048"
#
#   arg0 = part           (default xc7z020clg484-1)
#   arg1 = clock period ns (default 10.0  => 100 MHz)
#   arg2 = D list          (default "256 512 1024 2048")
#
# Results: results/dsweep/synth_D<D>.txt (one per D) + a combined summary.
# Requires the per-D item_mem .mem ROMs, which this script regenerates via
# python_ref/generate_vectors.py --core --D <D> before each synth.
# ===========================================================================

set part   "xc7z020clg484-1"
set period  10.0
set dlist   {256 512 1024 2048}

if {$argc >= 1} { set part   [lindex $argv 0] }
if {$argc >= 2} { set period [lindex $argv 1] }
if {$argc >= 3} { set dlist  [lindex $argv 2] }

set repo    [file normalize [file join [file dirname [info script]] ..]]
set outdir  [file join $repo results dsweep]
file mkdir $outdir

# Core RTL filelist (encoder + pruning_mask + AM + top), in compile order.
set rtl_files {
    rtl/item_mem.sv
    rtl/bundle_unit.sv
    rtl/encoder_top.sv
    rtl/pruning_mask.sv
    rtl/popcount_am.sv
    rtl/hdc_core_top.sv
}

set summary [open [file join $outdir summary.txt] w]
puts $summary "D-sweep OOC synthesis -- hdc_core_top"
puts $summary "part=$part  clock_period=${period}ns  ([expr {1000.0/$period}] MHz)"
puts $summary "Vivado: [version -short]"
puts $summary [string repeat "=" 78]
puts $summary [format "%-6s %-10s %-10s %-10s %-12s %-10s" \
    "D" "LUT" "FF" "DSP" "WNS(ns)" "Fmax(MHz)"]
puts $summary [string repeat "-" 78]

foreach D $dlist {
    set words [expr {$D / 64}]
    puts "==== D=$D  (WORDS=$words) ============================================"

    # 1) Regenerate per-D golden vectors so the item_mem .mem ROMs match D.
    set vecdir "python_ref/vectors/cosim_core_D${D}"
    set rc [catch {exec python python_ref/generate_vectors.py --core --D $D \
                     --count 50 --seed 42 --out-dir $vecdir} genout]
    if {$rc} {
        puts "ERROR: vector generation failed for D=$D:\n$genout"
        continue
    }
    puts $genout

    # 2) Fresh in-memory project, read RTL, synth OOC with WORDS override.
    create_project -in_memory -part $part
    foreach f $rtl_files { read_verilog -sv [file join $repo $f] }

    synth_design -top hdc_core_top -mode out_of_context \
        -generic WORDS=$words \
        -generic CH_MEM=[file join $repo $vecdir item_mem_channel.mem] \
        -generic FT_MEM=[file join $repo $vecdir item_mem_feature.mem] \
        -generic VAL_MEM=[file join $repo $vecdir item_mem_value.mem]

    create_clock -name clk -period $period [get_ports clk]

    # 3) Reports.
    set rpt [file join $outdir "synth_D${D}.txt"]
    report_utilization -file $rpt
    report_timing_summary -file $rpt -append

    # 4) Scrape headline numbers for the summary table.
    set luts [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == LUT}]]
    set ffs  [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == REGISTER}]]
    set dsps [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == ARITHMETIC}]]
    set wns  [get_property SLACK [get_timing_paths -delay_type max -nworst 1]]
    if {$wns eq "" || $wns eq "inf"} {
        set fmax "n/a"
    } else {
        set fmax [format "%.1f" [expr {1000.0 / ($period - $wns)}]]
    }
    puts $summary [format "%-6s %-10s %-10s %-10s %-12s %-10s" \
        $D $luts $ffs $dsps $wns $fmax]
    flush $summary

    close_project
}

puts $summary [string repeat "=" 78]
puts $summary "NOTE: OOC counts are core-only (no PS/DMA). Full-system utilisation"
puts $summary "      + bitstream timing come from the FInal_HDC place&route run."
close $summary
puts "Done. See [file join $outdir summary.txt]"
