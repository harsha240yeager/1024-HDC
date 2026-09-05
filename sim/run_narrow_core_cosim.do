# ===========================================================================
# run_narrow_core_cosim.do  --  narrow-core co-simulation (K_BITS=128, anchor C)
#
#   Regenerates the Python narrow-core golden vectors, compiles hdc_core_top_narrow
#   + popcount_am_narrow + hdc_sel_pkg, runs tb_core_narrow_cosim, reports PASS/FAIL.
#
# Run from the repository root:
#     vsim -c -do sim/run_narrow_core_cosim.do
#
# Optional: NUM_CASES env var (default 500), SEED env var (default 42).
#
# SEED must be 42 -- the deployed item-memory seed.  SEL comes from the seed-42
# pooled Fisher artefact, so at any other seed most selected positions are
# input-independent constants and the narrow datapath is barely exercised:
# measured at seed 31, only 46 of the 128 SEL positions are active, best-distance
# range collapses to 2..15 (mean 8.1), and 82 XOR lanes never toggle across the
# whole run.  At seed 42 all 128 are active and the range is 27..50 (mean 38.2).
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set SEED 42
if {[info exists ::env(SEED)]} { set SEED $::env(SEED) }

set VECDIR "python_ref/vectors/cosim_core_narrow"

echo "=== \[1/5\] Ensure anchor-C SEL package ==="
if {[catch {exec python3 scripts/gen_sel_table.py --keep 0.125} result]} {
    echo "ERROR: gen_sel_table failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/5\] Generating Python narrow-core golden vectors ($NUM_CASES cases, seed $SEED) ==="
if {[catch {exec python python_ref/generate_vectors.py --narrow-core --count $NUM_CASES --seed $SEED --out-dir $VECDIR} result]} {
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
