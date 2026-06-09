# ===========================================================================
# run_encoder_cosim.do  --  one-command encoder_top co-simulation harness
#
#   Regenerates the Python golden encoder vectors (+ item_mem .mem files),
#   compiles item_mem + bundle_unit + encoder_top + TB, runs the simulation,
#   and reports PASS/FAIL (non-zero exit on mismatch).
#
# Run from the repository root:
#     vsim -c -do sim/run_encoder_cosim.do
#
# Optional: set the case count via the NUM_CASES env var (default 500).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_encoder"

echo "=== \[1/4\] Generating Python golden encoder vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --encoder --count $NUM_CASES --seed 23 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling item_mem + bundle_unit + encoder_top + testbench ==="
vlog -sv -quiet rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv tb/tb_encoder_cosim.sv

echo "=== \[4/4\] Running encoder co-simulation ==="
vsim -quiet -t 1ps work.tb_encoder_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
