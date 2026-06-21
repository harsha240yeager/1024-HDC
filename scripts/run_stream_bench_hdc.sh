#!/usr/bin/env bash
# Phase 3 stream bench: program hdc_dma_stream_bench.elf, capture UART to results/.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HDC_ROOT="${HDC_ROOT:-/home/bsp-lab/Desktop/Final HDC/HDC_harsha}"
HDC_LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_stream_bench}"
RESULTS="${HDC_STREAM_BENCH_RESULTS:-$REPO/results/phase3/board_bench.txt}"
ELF="${HDC_STREAM_BENCH_ELF:-$HDC_ROOT/hdc_dma_stream_bench/build/hdc_dma_stream_bench.elf}"
SERIAL="${HDC_SERIAL:-/dev/ttyUSB1}"
BAUD="${HDC_SERIAL_BAUD:-115200}"

mkdir -p "$HDC_LOG_DIR" "$(dirname "$RESULTS")"

echo "=== HDC Phase 3 stream bench ==="
echo "  ELF:     $ELF"
echo "  serial:  $SERIAL @ $BAUD"
echo "  results: $RESULTS"

if [[ ! -f "$ELF" ]]; then
  echo "ERROR: missing $ELF" >&2
  echo "Build first: bash scripts/build_hdc_dma_stream_bench.sh" >&2
  exit 1
fi

if [[ -f "$HDC_ROOT/_ide/common.sh" ]]; then
  # shellcheck source=/dev/null
  source "$HDC_ROOT/_ide/common.sh"
  hdc_sync_final_1024_bitstream || true
  hdc_stop_conflicting_sessions || true
fi

LOG="$HDC_LOG_DIR/stream_bench_uart.log"

if command -v xsdb >/dev/null 2>&1 && [[ -f "$HDC_ROOT/_ide/program_pl_only.tcl" ]]; then
  echo "=== Program PL + run ELF via xsdb (see workspace tcl) ==="
  echo "If you use a custom run tcl, point HDC_STREAM_BENCH_TCL at it."
fi

if [[ -e "$SERIAL" ]] && command -v stty >/dev/null 2>&1; then
  stty -F "$SERIAL" "$BAUD" cs8 -cstopb -parenb raw -echo
  echo "=== Capture UART (30 s) — reset/run board now ==="
  timeout 30 cat "$SERIAL" | tee "$LOG" || true
else
  echo "WARN: serial $SERIAL not found; paste UART log into $RESULTS manually." >&2
  LOG=""
fi

{
  echo "# HDC Phase 3 stream bench (DMA path)"
  echo "# $(date -Iseconds 2>/dev/null || date)"
  echo "# ELF: $ELF"
  echo "# Device: xc7z020 ZedBoard, Phase 2 stream bitstream"
  echo ""
  if [[ -n "$LOG" && -f "$LOG" ]]; then
    cat "$LOG"
  else
    echo "(paste UART output here)"
  fi
} >"$RESULTS"

echo "Results saved: $RESULTS"
if [[ -f "$LOG" ]]; then
  grep -E "min  =|max  =|mean =|throughput|PASS:|FAIL:|batch DMA" "$RESULTS" || true
  if grep -q "PASS: 200/200 golden cases" "$RESULTS"; then
    echo "SUCCESS: Phase 3 bench golden check passed."
  else
    echo "WARN: golden PASS line not found — verify log." >&2
  fi
fi
