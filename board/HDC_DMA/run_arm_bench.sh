#!/usr/bin/env bash
# Cross-build (via build_sw.sh) and run ARM HDC timing bench on ZedBoard.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_arm_bench}"
RESULTS="$REPO/results/baselines/arm_hdc_board_timing.txt"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

ARM_ELF="$ROOT/app/build/Final_HDC_arm_bench.elf"
BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"

mkdir -p "$LOG_DIR" "$(dirname "$RESULTS")"

echo "=== ARM HDC bench (cross-compile + JTAG) ==="

echo "== Regenerate golden + item mem (seed 42, matched) =="
bash "$REPO/scripts/prep_arm_bench.sh"
python3 "$REPO/python_ref/tools/verify_arm_bench_golden.py" || {
  echo "ERROR: host golden verify failed — fix before board run" >&2
  exit 1
}

echo "== Cross-compile =="
bash "$REPO/scripts/build_arm_bench_cross.sh"

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL" "$ARM_ELF"; do
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
if ! hdc_wait_for_digilent_usb; then
  echo "WARNING: ZedBoard not detected — build OK, run this script when board is connected." >&2
  exit 2
fi

echo "=== Program + poll ARM bench ==="
if ! hdc_xsdb "$ROOT/_ide/run_arm_bench_all.tcl" | tee "$LOG_DIR/run_arm_bench.log"; then
  echo "ERROR: ARM bench failed (see $LOG_DIR/run_arm_bench.log)" >&2
  exit 1
fi

{
  echo "ARM HDC software baseline — on-board timing (ZedBoard Cortex-A9)"
  echo "================================================================"
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_arm_bench.c + sw/hdc_arm_ref.c (-O2)"
  echo "Method:     JTAG DDR readback @ 0x00100400 (magic 0xBEC00006)"
  echo "Run script: bash board/HDC_DMA/run_arm_bench.sh"
  echo "Compare:    results/phase3/board_bench.txt (PL DMA ~4 us/window batch)"
  echo ""
  grep -v "^$" "$LOG_DIR/run_arm_bench.log" | sed -n '/^==================================================/,$p'
  echo ""
  if grep -q "FAIL: golden spot-check" "$LOG_DIR/run_arm_bench.log"; then
    echo "Status: FAIL (golden spot-check)"
  else
    echo "Status: PASS"
  fi
} >"$RESULTS"

echo "Results saved: $RESULTS"
grep -E "min  =|max  =|mean =|throughput|PASS:|FAIL:" "$RESULTS" || true
if grep -q "FAIL: golden spot-check" "$LOG_DIR/run_arm_bench.log"; then
  echo "ERROR: golden spot-check failed" >&2
  exit 1
fi
echo "SUCCESS: ARM HDC board timing complete."
