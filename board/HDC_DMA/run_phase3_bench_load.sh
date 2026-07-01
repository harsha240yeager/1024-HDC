#!/usr/bin/env bash
# Phase 3: reload bench ELF only (PL must already be programmed). For energy
# measurement — avoids bitstream-program power spike during INA219 logging.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_phase3_bench_load}"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BENCH_ELF="$ROOT/app/build/Final_HDC_dma_bench.elf"

mkdir -p "$LOG_DIR"

if [[ ! -f "$BENCH_ELF" ]]; then
  echo "ERROR: missing $BENCH_ELF — run build_sw.sh first." >&2
  exit 1
fi

hdc_stop_conflicting_sessions || exit 1
hdc_source_tools
hdc_ensure_hw_server
hdc_wait_for_digilent_usb || exit 1

echo "=== Phase 3 bench load-only (no PL reprogram) ==="
if ! hdc_xsdb "$ROOT/_ide/run_bench_load.tcl" | tee "$LOG_DIR/run_bench_load.log"; then
  echo "ERROR: bench load failed (see $LOG_DIR/run_bench_load.log)" >&2
  exit 1
fi

if ! grep -qE "PASS: [0-9]+/[0-9]+ batch golden cases" "$LOG_DIR/run_bench_load.log"; then
  echo "ERROR: batch golden check failed" >&2
  exit 1
fi

echo "SUCCESS: Phase 3 bench load-only complete."
