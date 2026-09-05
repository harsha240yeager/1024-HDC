# ===========================================================================
# run_narrow_core_cosim_identity.do  --  identity regression (K_BITS=D, SEL[i]=i)
#
#   Builds hdc_sel_pkg with --identity, generates narrow-core vectors, compiles,
#   and runs tb_core_narrow_cosim.  With SEL[i]=i and K=D this must match an
#   unmasked full-width baseline classify (see docs/H1_narrow_datapath_design.md §8).
#
# Run from the repository root:
#     vsim -c -do sim/run_narrow_core_cosim_identity.do
# ===========================================================================

onerror {quit -code 3}

# Portable interpreter pick: on Windows `python3` is often the Microsoft Store
# stub, which exits non-zero instead of running.  Probe candidates and keep the
# first that actually reports Python 3.  Override with the PYTHON env var.
proc find_python {} {
    if {[info exists ::env(PYTHON)]} { return $::env(PYTHON) }
    foreach cand {python3 python py} {
        if {![catch {exec $cand -c "import sys; print(sys.version_info\[0\])"} out]} {
            if {[string trim $out] eq "3"} { return $cand }
        }
    }
    return ""
}

set PY [find_python]
if {$PY eq ""} {
    echo "ERROR: no working Python 3 found (tried python3, python, py)."
    echo "       Set the PYTHON env var to your interpreter and re-run."
    quit -code 2
}
echo "Using Python: $PY"

set NUM_CASES 500
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_core_narrow_identity"

echo "=== \[1/5\] Emit identity SEL package (K=D, SEL[i]=i) ==="
if {[catch {exec $PY scripts/gen_sel_table.py --identity} result]} {
    echo "ERROR: gen_sel_table --identity failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/5\] Generating identity narrow-core vectors ($NUM_CASES cases) ==="
if {[catch {exec $PY python_ref/generate_vectors.py --narrow-core --identity-sel --count $NUM_CASES --seed 31 --out-dir $VECDIR} result]} {
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

echo "=== \[5/5\] Running identity narrow co-simulation ==="
vsim -quiet -t 1ps work.tb_core_narrow_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR
run -all

echo "=== Restoring anchor-C SEL package ==="
if {[catch {exec $PY scripts/gen_sel_table.py --keep 0.125} result]} {
    echo "WARNING: failed to restore anchor-C hdc_sel_pkg.sv:"
    echo $result
} else {
    echo $result
}

quit -code 0
