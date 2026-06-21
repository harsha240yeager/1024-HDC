#!/usr/bin/env bash
# Run sw/hdc_dma_stream_golden_test.c on board; JTAG DDR readback @ 0x00100100.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_dma_golden_app}"
RESULTS="$REPO/results/phase2/board_golden_app.txt"
ARCHIVE_DIR="$REPO/results/phase2/logs"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
GOLDEN_ELF="$ROOT/app/build/Final_HDC_dma_golden.elf"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$RESULTS")"

echo "=== HDC_DMA Phase 2 golden app (bare-metal ELF) ==="

for f in "$BITSTREAM" "$PS7_INIT" "$GOLDEN_ELF"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f — run build.sh or build_sw.sh first." >&2
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

echo "=== Load golden ELF + poll ==="
if ! hdc_xsdb "$ROOT/_ide/run_golden_load.tcl" | tee "$LOG_DIR/run_golden_load.log"; then
  echo "ERROR: golden app failed (see $LOG_DIR/run_golden_load.log)" >&2
  exit 1
fi

if ! grep -qE "PASS: [0-9]+/[0-9]+ stream golden cases" "$LOG_DIR/run_golden_load.log"; then
  echo "ERROR: golden app did not report PASS" >&2
  exit 1
fi

{
  echo "Phase 2 — DMA stream golden app (ZedBoard)"
  echo "=========================================="
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_dma_stream_golden_test.c"
  echo "Method:     JTAG DDR readback @ 0x00100100 (magic 0xBEC00003)"
  echo "Run script: bash board/HDC_DMA/run_golden_app.sh"
  echo ""
  grep -v "^$" "$LOG_DIR/run_golden_load.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Status: PASS"
} >"$RESULTS"

cp -f "$LOG_DIR/program_pl.log" "$ARCHIVE_DIR/golden_app_program_pl.log"
cp -f "$LOG_DIR/run_golden_load.log" "$ARCHIVE_DIR/golden_app_run.log"

echo "Results saved: $RESULTS"
echo "Logs archived: $ARCHIVE_DIR/golden_app_*.log"
grep -E "PASS:|FAIL:" "$RESULTS" || true
echo "SUCCESS: Phase 2 golden app complete."
