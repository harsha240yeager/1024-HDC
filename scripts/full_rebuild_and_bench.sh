#!/usr/bin/env bash
# Kill stray jobs, rebuild synth→impl→export (0 critical warnings), BSP/ELFs, board bench.
set -euo pipefail

VIVADO_PROJ="${HDC_VIVADO_ROOT:-/home/bsp-lab/Final_HDC/FInal_HDC}"
BOARD="$HOME/1024-HDC/board/HDC_DMA"
LOG="$VIVADO_PROJ/full_pipeline.log"

echo "== Stop background tasks =="
pkill -f 'wait_for_log|run_impl_export.tcl|rebuild_from_synth.tcl' 2>/dev/null || true
pkill -f 'hw_server.*3121' 2>/dev/null || true
pgrep -af 'vivado -mode batch' | awk '{print $1}' | xargs -r kill 2>/dev/null || true
sleep 2

echo "== Vivado: synth → impl → export (gate: 0 critical warnings) =="
/cad/Xilinx/Vivado/2024.2/bin/vivado -mode batch -notrace \
  -source "$VIVADO_PROJ/rebuild_from_synth.tcl" \
  -log "$VIVADO_PROJ/rebuild_from_synth.log" 2>&1 | tee "$LOG"

# Double-check OOC + session logs
OOC_LOG="$VIVADO_PROJ/FInal_HDC.runs/design_1_hdc_stream_system_0_0_synth_1/runme.log"
if grep -E '^CRITICAL WARNING:' "$OOC_LOG" 2>/dev/null; then
  echo "ERROR: CRITICAL WARNING still present in $OOC_LOG" >&2
  exit 1
fi

echo "== Stage bitstream + build BSP/ELFs =="
export HDC_VIVADO_ROOT="$VIVADO_PROJ"
mkdir -p "$BOARD/platform/export/Final_HDC/hw" "$BOARD/app/_ide/bitstream"
cp -f "$VIVADO_PROJ/export/hw/design_1_wrapper.xsa" "$BOARD/platform/export/Final_HDC/hw/"
cp -f "$VIVADO_PROJ/FInal_HDC.runs/impl_1/design_1_wrapper.bit" "$BOARD/app/_ide/bitstream/"

source /cad/Xilinx/Vitis/2024.2/settings64.sh
bash "$BOARD/build_sw.sh"

echo "== Program board + Phase 3 bench =="
cd "$BOARD"
bash run_phase3_bench.sh 2>&1 | tee /tmp/hdc_phase3_bench/full_pipeline_bench.log

echo "SUCCESS: full pipeline complete."
