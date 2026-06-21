#!/usr/bin/env bash
# Phase 1 board bench: program hdc_core_bench.elf, JTAG readback @ 0x00100000.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HDC_ROOT="${HDC_ROOT:-/home/bsp-lab/Desktop/Final HDC/HDC_harsha}"
HDC_LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_bench}"
RESULTS="${HDC_BENCH_RESULTS:-$REPO/results/phase1/board_bench.txt}"

# shellcheck source=/dev/null
source "$HDC_ROOT/_ide/common.sh"

mkdir -p "$HDC_LOG_DIR" "$(dirname "$RESULTS")"

echo "=== HDC Phase 1 bench (program + JTAG readback) ==="
echo "  workspace: $HDC_ROOT"
echo "  results:   $RESULTS"

hdc_sync_final_1024_bitstream

for f in \
  "$HDC_FINAL1024_BITSTREAM" \
  "$HDC_FINAL1024_PS7_INIT" \
  "$HDC_FINAL1024_FSBL" \
  "$HDC_ROOT/hdc_core_bench/build/hdc_core_bench.elf"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f" >&2
    echo "Build ELF first (see README Phase 1 bench section)." >&2
    exit 1
  fi
done

hdc_stop_conflicting_sessions || exit 1
hdc_prepare_final_1024_jtag "$HDC_LOG_DIR"

echo "=== Program + poll bench (single JTAG session) ==="
hdc_xsdb "$HDC_ROOT/_ide/run_bench_all.tcl" | tee "$HDC_LOG_DIR/run_bench_all.log"

if ! grep -q "PASS: 200/200 golden cases" "$HDC_LOG_DIR/run_bench_all.log"; then
  echo "ERROR: bench run failed (see $HDC_LOG_DIR/run_bench_all.log)" >&2
  exit 1
fi

{
  echo "# HDC Phase 1 board results (JTAG readback from hdc_core_bench.elf @ 0x00100000)"
  echo "# $(date -Iseconds)"
  echo "# Path: AXI-Lite @ 100 MHz PL"
  echo "# Device: xc7z020 (ZedBoard)"
  echo ""
  grep -v "^$" "$HDC_LOG_DIR/run_bench_all.log" | sed -n '/^==================================================/,$p'
} >"$RESULTS"

echo "Results saved: $RESULTS"
grep -E "min  =|max  =|mean =|throughput|PASS:|FAIL:" "$RESULTS" || true
echo "SUCCESS: Phase 1 bench complete."
