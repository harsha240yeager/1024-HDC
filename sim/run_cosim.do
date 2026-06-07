# ===========================================================================
# run_cosim.do  --  one-command automated co-simulation harness
#
#   Regenerates the Python golden vectors, compiles the RTL + co-sim TB,
#   runs the simulation, and reports PASS/FAIL (non-zero exit on mismatch).
#
# Run from the repository root:
#     vsim -c -do sim/run_cosim.do
#
# Optional: set the case count via the NUM_CASES env var, e.g. (PowerShell)
#     $env:NUM_CASES=2000; vsim -c -do sim/run_cosim.do
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 1000
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim"

echo "=== \[1/4\] Generating Python golden vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --flat --count $NUM_CASES --seed 42 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling RTL + co-sim testbench ==="
vlog -sv -quiet rtl/permute_stage.sv rtl/xor_permute_top.sv tb/tb_cosim.sv

echo "=== \[4/4\] Running co-simulation ==="
vsim -quiet -t 1ps work.tb_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

# Reached only if the TB ended via $finish (all cases passed).
quit -code 0
