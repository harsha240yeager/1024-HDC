#!/usr/bin/env bash
# Narrow PL latency bench: program narrow bitstream, run DMA bench, save results.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_narrow_bench}"
RESULTS="${HDC_BENCH_RESULTS:-$REPO/results/protocol_v2/narrow_rtl/board_bench.txt}"
ARCHIVE_DIR="$REPO/results/protocol_v2/narrow_rtl/logs"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"
# shellcheck source=/dev/null
source "$ROOT/_ide/bitstream_switch.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"
BENCH_ELF="$ROOT/app/build/Final_HDC_dma_bench_narrow.elf"

unset HDC_VIVADO_ROOT

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$RESULTS")"

echo "=== Narrow golden vectors ==="
bash "$REPO/scripts/prep_narrow_golden_test.sh"

echo "=== Build narrow bench ELF ==="
bash "$ROOT/build_narrow_bench.sh"

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL" "$BENCH_ELF"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f" >&2
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

hdc_activate_narrow_bitstream
trap 'hdc_restore_baseline_bitstream' EXIT

echo "=== Program narrow PL + run bench ==="
if ! hdc_xsdb "$ROOT/_ide/run_bench_narrow_all.tcl" | tee "$LOG_DIR/run_narrow_bench.log"; then
  echo "ERROR: narrow bench failed (see $LOG_DIR/run_narrow_bench.log)" >&2
  exit 1
fi

if ! grep -qE "PASS: [0-9]+/[0-9]+ batch golden cases" "$LOG_DIR/run_narrow_bench.log"; then
  echo "ERROR: batch golden check failed" >&2
  exit 1
fi
if ! grep -qE "PASS: [0-9]+/[0-9]+ stream golden cases" "$LOG_DIR/run_narrow_bench.log"; then
  echo "ERROR: per-window golden check failed" >&2
  exit 1
fi

{
  echo "Narrow PL — DMA stream bench (ZedBoard, K=128, keep=0.125)"
  echo "============================================================"
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_dma_stream_bench.c (-DHDC_NARROW)"
  echo "Golden:     sw/golden_vectors_narrow.h"
  echo "Method:     JTAG readback @ 0x00100000 (single) + 0x00100100 (batch)"
  echo "Run script: bash board/HDC_DMA/run_narrow_phase3_bench.sh"
  echo "Bitstream:  $BITSTREAM"
  echo "Baseline:   results/phase3/board_bench.txt (~4.63 us/window batch mean)"
  echo ""
  grep -v "^$" "$LOG_DIR/run_narrow_bench.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Status: PASS"
} >"$RESULTS"

cp -f "$LOG_DIR/run_narrow_bench.log" "$ARCHIVE_DIR/narrow_bench_run.log"

echo "Results saved: $RESULTS"
grep -E "min  =|max  =|mean =|total   =|mean/window|batch golden|stream golden" "$RESULTS" || true
echo "SUCCESS: Narrow Phase 3 bench complete."
