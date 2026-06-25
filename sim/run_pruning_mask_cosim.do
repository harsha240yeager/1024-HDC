# ===========================================================================
# run_pruning_mask_cosim.do  --  one-command pruning_mask co-simulation harness
#
#   Regenerates the Python golden pruning-mask vectors, compiles pruning_mask +
#   TB, runs the simulation, and reports PASS/FAIL (non-zero exit on mismatch).
#
# Run from the repository root:
#     vsim -c -do sim/run_pruning_mask_cosim.do
#
# Optional: set the case count via the NUM_CASES env var (default 64).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 64
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_pruning_mask"

echo "=== \[1/4\] Generating Python golden pruning-mask vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --pruning-mask --count $NUM_CASES --seed 7 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling pruning_mask + testbench ==="
vlog -sv -quiet rtl/pruning_mask.sv tb/tb_pruning_mask_cosim.sv

echo "=== \[4/4\] Running pruning_mask co-simulation ==="
vsim -quiet -t 1ps work.tb_pruning_mask_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
