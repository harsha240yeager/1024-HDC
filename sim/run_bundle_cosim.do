# ===========================================================================
# run_bundle_cosim.do  --  one-command bundle_unit co-simulation harness
#
#   Regenerates the Python golden bundle vectors, compiles bundle_unit + TB,
#   runs the simulation, and reports PASS/FAIL (non-zero exit on mismatch).
#
# Run from the repository root:
#     vsim -c -do sim/run_bundle_cosim.do
#
# Optional: set the case count via the NUM_CASES env var (default 500).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_bundle"

echo "=== \[1/4\] Generating Python golden bundle vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --bundle --count $NUM_CASES --seed 7 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling bundle_unit + testbench ==="
vlog -sv -quiet rtl/bundle_unit.sv tb/tb_bundle_cosim.sv

echo "=== \[4/4\] Running bundle co-simulation ==="
vsim -quiet -t 1ps work.tb_bundle_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
