# ===========================================================================
# run_stream_cosim_debug.do  --  stream co-sim WITH functional-verification trace
#
#   Same as run_stream_cosim.do but enables debug logging, traces the first 3
#   cases step-by-step, and dumps a VCD waveform for GUI review.
#
# Run from the repository root:
#     vsim -c -do sim/run_stream_cosim_debug.do
#
# Open the waveform in the GUI afterward:
#     vsim -gui -view sim/waves/stream_cosim.vcd
#
# Key signals to add in ModelSim wave window:
#   /tb_stream_cosim/s_tvalid /s_tready /s_tdata /s_tlast
#   /tb_stream_cosim/m_tvalid /m_tready /m_tdata /m_tlast
#   /tb_stream_cosim/dut/dbg_fsm_state /dbg_beat /dbg_levels_flat
#   /tb_stream_cosim/dut/dbg_core_start /dbg_core_busy /dbg_core_out_valid
#   /tb_stream_cosim/dut/dbg_class_idx /dbg_class_dist
#   /tb_stream_cosim/dut/u_core/u_encoder/busy /out_valid
#   /tb_stream_cosim/dut/u_core/u_am/best_idx /best_dist
# ===========================================================================

onerror {quit -code 3}

set NUM_CASES 10
if {[info exists ::env(NUM_CASES)]} { set NUM_CASES $::env(NUM_CASES) }

set VECDIR "python_ref/vectors/cosim_core"

echo "=== \[1/4\] Generating Python golden vectors ($NUM_CASES cases) ==="
if {[catch {exec python python_ref/generate_vectors.py --core --count $NUM_CASES --seed 31 --out-dir $VECDIR} result]} {
    echo "ERROR: vector generation failed:"
    echo $result
    quit -code 2
}
echo $result

echo "=== \[2/4\] Creating work library ==="
if {[file exists work]} { vdel -all -lib work }
vlib work

echo "=== \[3/4\] Compiling full core + AXI4-Stream wrapper + testbench ==="
vlog -sv -quiet rtl/item_mem.sv rtl/bundle_unit.sv rtl/encoder_top.sv rtl/popcount_am.sv rtl/hdc_core_top.sv rtl/hdc_stream_wrapper.sv tb/tb_stream_cosim.sv

echo "=== \[4/4\] Running stream co-sim with +DEBUG +TRACE=3 +WAVE ==="
vsim -t 1ps work.tb_stream_cosim +CASES=$NUM_CASES +VECDIR=$VECDIR +DEBUG +TRACE=3 +WAVE
run -all

quit -code 0
