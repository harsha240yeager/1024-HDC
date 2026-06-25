# ===========================================================================
# run_dsweep_cosim.do  --  functional D-parameterization sweep of hdc_core_top
#
#   For each D in {256, 512, 1024, 2048} (WORDS = D/64): regenerate the Python
#   golden core vectors at that D, then run tb_core_cosim with the matching
#   WORDS + item_mem .mem overrides and check bit-exact PASS/FAIL.
#
#   Proves the whole datapath (item_mem -> encoder -> pruning_mask -> popcount_am)
#   is correct at every swept D, before the synthesis sweep (scripts/dsweep_synth.tcl).
#
# Run from the repository root:
#     vsim -c -do sim/run_dsweep_cosim.do
#
# Optional: NUM_CASES env var (default 200), DSWEEP_DLIST env var
#           (default "256 512 1024 2048").
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 200
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set DLIST {256 512 1024 2048}
if {[info exists ::env(DSWEEP_DLIST)]} { set DLIST $::env(DSWEEP_DLIST) }

echo "=== Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== Compiling parameterized core + testbench ==="
vlog -sv -quiet rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv \
                rtl/pruning_mask.sv rtl/popcount_am.sv rtl/hdc_core_top.sv \
                tb/tb_core_cosim.sv

set fail 0
foreach D $DLIST {
    set words [expr {$D / 64}]
    set vecdir "python_ref/vectors/cosim_core_D${D}"

    echo "=================================================================="
    echo "=== D=$D  (WORDS=$words)  CASES=$NUM_CASES ==="
    echo "=================================================================="

    echo "--- Generating Python golden core vectors (D=$D) ---"
    if {[catch {exec python python_ref/generate_vectors.py --core --D $D \
                  --count $NUM_CASES --seed 42 --out-dir $vecdir} result]} {
        echo "ERROR: vector generation failed for D=$D:"
        echo $result
        set fail 1
        continue
    }
    echo $result

    echo "--- Running tb_core_cosim (D=$D) ---"
    set sim_ok 0
    if {![catch {vsim -c -quiet -t 1ps work.tb_core_cosim \
        -gWORDS=$words \
        -gCH_MEM=$vecdir/item_mem_channel.mem \
        -gFT_MEM=$vecdir/item_mem_feature.mem \
        -gVAL_MEM=$vecdir/item_mem_value.mem \
        +CASES=$NUM_CASES +VECDIR=$vecdir \
        -do "run -all; quit -sim"} simout]} {
        if {[string match *PASS:* $simout]} {
            set sim_ok 1
            echo $simout
        } else {
            echo $simout
        }
    } else {
        echo "ERROR: simulation failed for D=$D:"
        echo $simout
    }

    if {!$sim_ok} {
        echo "FAIL: D=$D functional cosim did not PASS."
        set fail 1
    } else {
        echo "PASS: D=$D functional cosim."
    }
}

if {$fail} {
    echo "D-sweep functional cosim: one or more D points FAILED to generate/run."
    quit -code 2
}
echo "D-sweep functional cosim complete (see per-D PASS lines above)."
quit -code 0
