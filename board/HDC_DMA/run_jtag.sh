#!/usr/bin/env bash
# Program HDC_DMA Phase 2 and run 200-case stream golden test over JTAG (no UART).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_dma_jtag}"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"
GOLDEN_VECDIR="${HDC_GOLDEN_VECDIR:-$REPO/python_ref/vectors/cosim_core}"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    echo "Syncing newer Vivado bitstream..."
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR"
export HDC_IDE="$ROOT/_ide"
export HDC_GOLDEN_VECDIR

echo "=== HDC_DMA Phase 2 JTAG golden test ==="
echo "  root:    $ROOT"
echo "  vectors: $GOLDEN_VECDIR"
echo "  log dir: $LOG_DIR"

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f — run build.sh first." >&2
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

echo "=== Programming PL (no application) ==="
if ! hdc_xsdb "$ROOT/_ide/program_pl.tcl" | tee "$LOG_DIR/program_pl.log"; then
  echo "ERROR: PL programming failed" >&2
  exit 1
fi

echo "=== Running stream golden test over JTAG ==="
if ! hdc_xsdb "$REPO/scripts/run_stream_golden_jtag.tcl" | tee "$LOG_DIR/stream_golden_jtag.log"; then
  echo "ERROR: JTAG golden test failed (see $LOG_DIR/stream_golden_jtag.log)" >&2
  exit 1
fi

if grep -qE "PASS: [0-9]+/[0-9]+ stream golden cases" "$LOG_DIR/stream_golden_jtag.log"; then
  grep -E "PASS: [0-9]+/[0-9]+ stream golden cases" "$LOG_DIR/stream_golden_jtag.log"
  echo "SUCCESS"
  exit 0
fi

echo "ERROR: golden test did not report PASS" >&2
exit 1
