# ===========================================================================
# run_core_cosim.do  --  one-command hdc_core_top co-simulation harness
#
#   Regenerates the Python golden end-to-end vectors (item_mem .mem files,
#   trained prototypes, mask, level grids, expected labels), compiles the
#   full core (item_mem + bundle_unit + encoder_top + popcount_am +
#   hdc_core_top) + TB, runs the simulation, and reports PASS/FAIL
#   (non-zero exit on mismatch).
#
# Run from the repository root:
#     vsim -c -do sim/run_core_cosim.do
#
# Optional: set the case count via the NUM_CASES env var (default 500).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_core"

echo "=== \[1/4\] Generating Python golden end-to-end vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --core --count $NUM_CASES --seed 31 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling full core + testbench ==="
vlog -sv -quiet rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv rtl/pruning_mask.sv rtl/popcount_am.sv rtl/hdc_core_top.sv tb/tb_core_cosim.sv

echo "=== \[4/4\] Running end-to-end core co-simulation ==="
vsim -quiet -t 1ps work.tb_core_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
