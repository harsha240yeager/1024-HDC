# ===========================================================================
# run_narrow_core_cosim.do  --  narrow-core co-simulation (K_BITS=128, anchor C)
#
#   Regenerates the Python narrow-core golden vectors, compiles hdc_core_top_narrow
#   + popcount_am_narrow + hdc_sel_pkg, runs tb_core_narrow_cosim, reports PASS/FAIL.
#
# Run from the repository root:
#     vsim -c -do sim/run_narrow_core_cosim.do
#
# Optional: NUM_CASES env var (default 500).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_core_narrow"

echo "=== \[1/5\] Ensure anchor-C SEL package ==="
if {[catch {exec python3 scripts/gen_sel_table.py --keep 0.125} result]} {
    echo "ERROR: gen_sel_table failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/5\] Generating Python narrow-core golden vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --narrow-core --count $NUM_CASES --seed 31 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[3/5\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[4/5\] Compiling narrow core + testbench ==="
vlog -sv -quiet rtl/hdc_sel_pkg.sv rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv rtl/popcount_am_narrow.sv rtl/hdc_core_top_narrow.sv tb/tb_core_narrow_cosim.sv

echo "=== \[5/5\] Running narrow end-to-end co-simulation ==="
vsim -quiet -t 1ps work.tb_core_narrow_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
