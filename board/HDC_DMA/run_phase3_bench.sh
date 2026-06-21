#!/usr/bin/env bash
# Phase 3: run sw/hdc_dma_stream_bench.c (single + batch DMA + golden), save results/phase3/board_bench.txt
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_phase3_bench}"
RESULTS="$REPO/results/phase3/board_bench.txt"
ARCHIVE_DIR="$REPO/results/phase3/logs"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"
BENCH_ELF="$ROOT/app/build/Final_HDC_dma_bench.elf"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$RESULTS")"

echo "=== HDC Phase 3 bench (hdc_dma_stream_bench.c) ==="

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL" "$BENCH_ELF"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f — run build_sw.sh first." >&2
    exit 1
  fi
done

hdc_stop_conflicting_sessions || exit 1
hdc_source_tools
hdc_stop_hw_server
sleep 2
hdc_start_hw_server || exit 1
sleep 2
hdc_wait_for_digilent_usb || exit 1

echo "=== Program + poll Phase 3 bench ==="
if ! hdc_xsdb "$ROOT/_ide/run_bench_all.tcl" | tee "$LOG_DIR/run_phase3_bench.log"; then
  echo "ERROR: Phase 3 bench failed (see $LOG_DIR/run_phase3_bench.log)" >&2
  exit 1
fi

if ! grep -qE "PASS: [0-9]+/[0-9]+ batch golden cases" "$LOG_DIR/run_phase3_bench.log"; then
  echo "ERROR: batch golden check failed" >&2
  exit 1
fi
if ! grep -qE "PASS: [0-9]+/[0-9]+ stream golden cases" "$LOG_DIR/run_phase3_bench.log"; then
  echo "ERROR: per-window golden check failed" >&2
  exit 1
fi

{
  echo "Phase 3 — DMA stream bench (ZedBoard)"
  echo "====================================="
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_dma_stream_bench.c"
  echo "Method:     JTAG readback @ 0x00100000 (single) + 0x00100100 (batch)"
  echo "Run script: bash board/HDC_DMA/run_phase3_bench.sh"
  echo "Phase 1 baseline: ~3 us/window (AXI-Lite poll)"
  echo ""
  grep -v "^$" "$LOG_DIR/run_phase3_bench.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Status: PASS"
} >"$RESULTS"

cp -f "$LOG_DIR/run_phase3_bench.log" "$ARCHIVE_DIR/board_bench_run.log"

echo "Results saved: $RESULTS"
grep -E "min  =|max  =|mean =|Batch DMA|batch golden|stream golden|throughput" "$RESULTS" || true
echo "SUCCESS: Phase 3 bench complete."
