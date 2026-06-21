#!/usr/bin/env bash
# Phase 3 optional regression: golden app → results/phase3/board_golden.txt
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_phase3_golden}"
RESULTS="$REPO/results/phase3/board_golden.txt"
ARCHIVE_DIR="$REPO/results/phase3/logs"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
GOLDEN_ELF="$ROOT/app/build/Final_HDC_dma_golden.elf"

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$RESULTS")"

echo "=== HDC Phase 3 golden regression ==="

for f in "$BITSTREAM" "$PS7_INIT" "$GOLDEN_ELF"; do
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

if ! hdc_xsdb "$ROOT/_ide/program_pl.tcl" | tee "$LOG_DIR/program_pl.log"; then
  echo "ERROR: PL programming failed" >&2
  exit 1
fi

if ! hdc_xsdb "$ROOT/_ide/run_golden_load.tcl" | tee "$LOG_DIR/run_golden.log"; then
  echo "ERROR: golden regression failed" >&2
  exit 1
fi

{
  echo "Phase 3 — DMA stream golden regression (ZedBoard)"
  echo "=================================================="
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_dma_stream_golden_test.c"
  echo "Method:     JTAG DDR readback @ 0x00100100"
  echo "Run script: bash board/HDC_DMA/run_phase3_golden.sh"
  echo ""
  grep -v "^$" "$LOG_DIR/run_golden.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Status: PASS"
} >"$RESULTS"

cp -f "$LOG_DIR/run_golden.log" "$ARCHIVE_DIR/board_golden_run.log"

echo "Results saved: $RESULTS"
grep -E "PASS:|FAIL:" "$RESULTS" || true
