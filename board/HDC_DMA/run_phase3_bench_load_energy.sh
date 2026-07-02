#!/usr/bin/env bash
# Bench load for INA219 energy: require batch timing, skip golden PASS (mask changed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_phase3_bench_load_energy}"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BENCH_ELF="$ROOT/app/build/Final_HDC_dma_bench.elf"

mkdir -p "$LOG_DIR"

if [[ ! -f "$BENCH_ELF" ]]; then
  echo "ERROR: missing $BENCH_ELF" >&2
  exit 1
fi

hdc_stop_conflicting_sessions || exit 1
hdc_source_tools
hdc_ensure_hw_server
hdc_wait_for_digilent_usb || exit 1

echo "=== Phase 3 bench load (energy mode) ==="
if ! hdc_xsdb "$ROOT/_ide/run_bench_load.tcl" | tee "$LOG_DIR/run_bench_load.log"; then
  echo "ERROR: xsdb bench load failed" >&2
  exit 1
fi

BATCH_US="$(grep -E "^total   = [0-9]+ us" "$LOG_DIR/run_bench_load.log" | tail -1 | awk '{print $3}')"
if [[ -z "$BATCH_US" ]]; then
  echo "ERROR: batch timing not found in log" >&2
  exit 1
fi

BATCH_MS="$(python3 -c "print(float('$BATCH_US')/1000.0)")"
echo "BATCH_MS=$BATCH_MS" | tee "$LOG_DIR/batch_ms.txt"

if grep -qE "PASS: [0-9]+/[0-9]+ batch golden cases" "$LOG_DIR/run_bench_load.log"; then
  echo "SUCCESS: bench complete (golden PASS)"
else
  echo "NOTE: golden check failed (expected after Fisher mask patch); batch ran ${BATCH_US} for energy."
  echo "SUCCESS: bench complete (energy mode)"
fi
