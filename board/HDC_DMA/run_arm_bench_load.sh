#!/usr/bin/env bash
# Load ARM bench ELF only (PL already programmed). For INA219 dynamic capture.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_arm_bench_load}"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

ARM_ELF="$ROOT/app/build/Final_HDC_arm_bench.elf"

mkdir -p "$LOG_DIR"

if [[ ! -f "$ARM_ELF" ]]; then
  echo "ERROR: missing $ARM_ELF — run build_sw.sh / build_arm_bench_cross.sh first." >&2
  exit 1
fi

hdc_stop_conflicting_sessions || exit 1
hdc_source_tools
hdc_ensure_hw_server
hdc_wait_for_digilent_usb || exit 1

echo "=== ARM bench load-only (no PL reprogram) ==="
if ! hdc_xsdb "$ROOT/_ide/run_arm_bench_load.tcl" | tee "$LOG_DIR/run_arm_bench_load.log"; then
  echo "ERROR: ARM bench load failed" >&2
  exit 1
fi

if ! grep -qE "PASS: 200/200 golden cases \(ARM infer\)" "$LOG_DIR/run_arm_bench_load.log"; then
  echo "ERROR: ARM golden check failed" >&2
  exit 1
fi

# Parse batch duration for energy integration (UART line from hdc_arm_bench.c)
BATCH_US="$(grep -E "ARM HDC batch: n=" "$LOG_DIR/run_arm_bench_load.log" | tail -1 | sed -n 's/.*total=\([0-9]*\) us.*/\1/p')"
if [[ -n "$BATCH_US" ]]; then
  echo "ARM batch_us=$BATCH_US" | tee "$LOG_DIR/arm_batch_us.txt"
fi

echo "SUCCESS: ARM bench load-only complete."
