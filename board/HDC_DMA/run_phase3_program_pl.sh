#!/usr/bin/env bash
# Program PL + FSBL only (CPU halted). Use before static INA219 idle measurement.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_phase3_program}"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR"

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL"; do
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

echo "=== Program PL only (idle static baseline) ==="
if ! hdc_xsdb "$ROOT/_ide/program_pl.tcl" | tee "$LOG_DIR/program_pl.log"; then
  echo "ERROR: PL program failed" >&2
  exit 1
fi

echo "SUCCESS: PL programmed, CPU halted — ready for static power log."
