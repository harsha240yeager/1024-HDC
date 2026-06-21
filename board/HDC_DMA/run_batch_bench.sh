#!/usr/bin/env bash
# Phase 3: sustained batch throughput + E2E latency proxy via JTAG readback.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_dma_batch_bench}"
RESULTS="$REPO/results/phase3/board_batch_bench.txt"
ARCHIVE_DIR="$REPO/results/phase3/logs"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
BATCH_ELF="$ROOT/app/build/Final_HDC_dma_batch_bench.elf"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$RESULTS")"

echo "=== HDC Phase 3 batch bench ==="

for f in "$BITSTREAM" "$PS7_INIT" "$BATCH_ELF"; do
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

echo "=== Program PL ==="
if ! hdc_xsdb "$ROOT/_ide/program_pl.tcl" | tee "$LOG_DIR/program_pl.log"; then
  echo "ERROR: PL programming failed" >&2
  exit 1
fi

echo "=== Load batch bench ELF + poll ==="
if ! hdc_xsdb "$ROOT/_ide/run_batch_bench_load.tcl" | tee "$LOG_DIR/run_batch_bench.log"; then
  echo "ERROR: batch bench failed (see $LOG_DIR/run_batch_bench.log)" >&2
  exit 1
fi

{
  echo "Phase 3 — DMA stream batch bench (ZedBoard)"
  echo "==========================================="
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_dma_stream_batch_bench.c"
  echo "Method:     JTAG DDR readback @ 0x00100200 (magic 0xBEC00004)"
  echo "Run script: bash board/HDC_DMA/run_batch_bench.sh"
  echo "Note:       Sustained = N sequential single-window DMA xfers (proto once)."
  echo "            E2E proxy = global timer MM2S+S2MM submit through both idle."
  echo ""
  grep -v "^$" "$LOG_DIR/run_batch_bench.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Status: PASS"
} >"$RESULTS"

cp -f "$LOG_DIR/program_pl.log" "$ARCHIVE_DIR/batch_bench_program_pl.log"
cp -f "$LOG_DIR/run_batch_bench.log" "$ARCHIVE_DIR/batch_bench_run.log"

echo "Results saved: $RESULTS"
grep -E "total =|mean =|throughput|E2E" "$RESULTS" || true
echo "SUCCESS: Phase 3 batch bench complete."
