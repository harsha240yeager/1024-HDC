# ===========================================================================
# run_am_cosim.do  --  one-command popcount_am co-simulation harness
#
#   Regenerates the Python golden AM vectors, compiles popcount_am + TB,
#   runs the simulation, and reports PASS/FAIL (non-zero exit on mismatch).
#
# Run from the repository root:
#     vsim -c -do sim/run_am_cosim.do
#
# Optional: set the case count via the NUM_CASES env var (default 500).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_am"

echo "=== \[1/4\] Generating Python golden AM vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --am --count $NUM_CASES --seed 11 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling popcount_am + testbench ==="
vlog -sv -quiet rtl/pruning_mask.sv rtl/popcount_am.sv tb/tb_am_cosim.sv

echo "=== \[4/4\] Running AM co-simulation ==="
vsim -quiet -t 1ps work.tb_am_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
