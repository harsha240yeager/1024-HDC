#!/usr/bin/env bash
# Program ZedBoard with HDC_DMA Phase 2 bitstream + DMA golden test app.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"
APP="$ROOT/app/build/Final_HDC_dma_golden.elf"
PROGRAM_TCL="$ROOT/_ide/program_board.tcl"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    echo "Syncing newer Vivado bitstream..."
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

for f in "$BITSTREAM" "$FSBL" "$APP"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing $f — run build.sh first." >&2
    exit 1
  fi
done

hdc_stop_conflicting_sessions || exit 1
hdc_source_tools
hdc_ensure_hw_server
hdc_wait_for_digilent_usb || exit 1

echo "Programming HDC_DMA (Phase 2 DMA app)..."
hdc_xsdb "$PROGRAM_TCL"
echo "Done. UART @ 115200 on /dev/ttyUSB0 — expect: PASS: 200/200 stream golden cases"
