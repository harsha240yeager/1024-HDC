#!/usr/bin/env bash
# Program Final_HDC_dma_bench.elf, poll @ 0x00100000 via JTAG, save phase2 bench results.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_dma_bench}"
RESULTS="$REPO/results/phase2/board_bench.txt"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"
BENCH_ELF="$ROOT/app/build/Final_HDC_dma_bench.elf"

if [[ -n "$HDC_VIVADO_ROOT" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR" "$(dirname "$RESULTS")"

echo "=== HDC_DMA Phase 2 bench (program + JTAG readback) ==="

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL" "$BENCH_ELF"; do
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

echo "=== Program + poll bench (single JTAG session) ==="
if ! hdc_xsdb "$ROOT/_ide/run_bench_all.tcl" | tee "$LOG_DIR/run_bench_all.log"; then
  echo "ERROR: bench run failed (see $LOG_DIR/run_bench_all.log)" >&2
  exit 1
fi

if ! grep -qE "PASS: [0-9]+/[0-9]+ stream golden cases" "$LOG_DIR/run_bench_all.log"; then
  echo "ERROR: golden spot-check failed during bench" >&2
  exit 1
fi

{
  echo "Phase 2 — DMA stream latency bench (ZedBoard)"
  echo "============================================="
  echo "Date:       $(date -Iseconds)"
  echo "Bitstream:  design_1, hdc_stream_system_bd_wrapper + axi_dma_0"
  echo "App:        sw/hdc_dma_stream_bench.c + sw/hdc_dma_stream.c"
  echo "Method:     JTAG readback @ 0x00100000"
  echo "Run script: bash board/HDC_DMA/run_bench.sh"
  echo "Phase 1 baseline: ~3 us/window (AXI-Lite poll)"
  echo ""
  grep -v "^$" "$LOG_DIR/run_bench_all.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Status: PASS"
} >"$RESULTS"

echo "Results saved: $RESULTS"
grep -E "min  =|max  =|mean =|throughput|delta =|PASS:|FAIL:" "$RESULTS" || true
echo "SUCCESS: Phase 2 bench complete."
