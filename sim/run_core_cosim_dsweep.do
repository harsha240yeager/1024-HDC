# ===========================================================================
# run_core_cosim_dsweep.do  --  single-D end-to-end core co-simulation
#
#   Same as run_core_cosim.do, but the hypervector dimension D is taken from
#   the DSWEEP_D environment variable so the whole datapath can be swept over
#   D in {256, 512, 1024, 2048}.  WORDS = D / 64 is overridden at elaboration
#   (-gWORDS=...), and the Python golden vectors (incl. item_mem .mem) are
#   regenerated at the same D so the co-sim stays bit-exact.
#
#   Driven once per D by scripts/run_dsweep_cosim.{ps1,sh}; can also be run
#   directly:
#       DSWEEP_D=512 vsim -c -do sim/run_core_cosim_dsweep.do   (bash)
#       $env:DSWEEP_D=512; vsim -c -do sim/run_core_cosim_dsweep.do  (pwsh)
#
#   Env: DSWEEP_D (default 1024), NUM_CASES (default 500).
# ===========================================================================

onerror {quit -code 3}

set DVAL 1024
if {[info exists ::env(DSWEEP_D)]} { set DVAL $::env(DSWEEP_D) }

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

if {[expr {$DVAL % 64}] != 0} {
    echo "ERROR: DSWEEP_D=$DVAL is not a multiple of 64 (BITS_PER_WORD)."
    quit -code 2
}
set WVAL [expr {$DVAL / 64}]
set VECDIR "python_ref/vectors/cosim_core"

echo "=== \[1/4\] Generating golden end-to-end vectors (D=$DVAL, WORDS=$WVAL, $NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --core --D $DVAL --count $NUM_CASES --seed 31 --out-dir $VECDIR} result]} {
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

echo "=== \[4/4\] Running core co-simulation at D=$DVAL ==="
vsim -quiet -t 1ps -gWORDS=$WVAL work.tb_core_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

quit -code 0
