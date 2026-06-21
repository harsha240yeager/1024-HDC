#!/usr/bin/env bash
# Program PL and run 200-case HDC golden test over JTAG (no UART).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HDC_ROOT="${HDC_ROOT:-/home/bsp-lab/Desktop/Final HDC/HDC_harsha}"
HDC_LOG_DIR="${HDC_LOG_DIR:-/tmp/golden_jtag_hdc}"
HDC_GOLDEN_VECDIR="${HDC_GOLDEN_VECDIR:-$REPO/python_ref/vectors/cosim_core}"

# shellcheck source=/dev/null
source "$HDC_ROOT/_ide/common.sh"

mkdir -p "$HDC_LOG_DIR"
export HDC_IDE="$HDC_ROOT/_ide"
export HDC_GOLDEN_VECDIR

echo "=== HDC JTAG golden test (200 cases, no UART) ==="
echo "  vectors: $HDC_GOLDEN_VECDIR"
echo "  log dir: $HDC_LOG_DIR"

hdc_sync_final_1024_bitstream

for f in "$HDC_FINAL1024_BITSTREAM" "$HDC_FINAL1024_PS7_INIT"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f" >&2
    exit 1
  fi
done

hdc_stop_conflicting_sessions || exit 1
hdc_prepare_final_1024_jtag "$HDC_LOG_DIR"

echo "=== Programming PL (no application) ==="
if ! hdc_xsdb "$HDC_ROOT/_ide/program_pl_only.tcl" | tee "$HDC_LOG_DIR/program_pl.log"; then
  echo "ERROR: PL programming failed" >&2
  exit 1
fi

echo "=== Running JTAG golden test ==="
if ! hdc_xsdb "$REPO/scripts/run_golden_jtag.tcl" | tee "$HDC_LOG_DIR/golden_jtag.log"; then
  echo "ERROR: JTAG golden test failed (see $HDC_LOG_DIR/golden_jtag.log)" >&2
  exit 1
fi

if grep -q "PASS: 200/200 golden cases" "$HDC_LOG_DIR/golden_jtag.log"; then
  echo "SUCCESS: PASS: 200/200 golden cases"
  exit 0
fi

if grep -qE "PASS: [0-9]+/[0-9]+ golden cases" "$HDC_LOG_DIR/golden_jtag.log"; then
  grep -E "PASS: [0-9]+/[0-9]+ golden cases" "$HDC_LOG_DIR/golden_jtag.log"
  exit 0
fi

echo "ERROR: golden test did not report PASS" >&2
exit 1
