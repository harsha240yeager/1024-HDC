#!/usr/bin/env bash
# Phase 3: run sw/hdc_emg_board_test.c (EMG replay), save results/phase3/board_emg_replay.txt
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_phase3_emg}"
RESULTS="$REPO/results/phase3/board_emg_replay.txt"
ARCHIVE_DIR="$REPO/results/phase3/logs"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

BITSTREAM="$ROOT/app/_ide/bitstream/design_1_wrapper.bit"
PS7_INIT="$ROOT/app/_ide/psinit/ps7_init.tcl"
FSBL="$ROOT/platform/zynq_fsbl/fsbl.elf"
EMG_ELF="$ROOT/app/build/Final_HDC_dma_emg.elf"
EMG_HEADER="$REPO/sw/emg_board_vectors.h"

if [[ -n "${HDC_VIVADO_ROOT:-}" && -f "$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit" ]]; then
  IMPL_BITSTREAM="$HDC_VIVADO_ROOT/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
  if [[ ! -f "$BITSTREAM" ]] \
    || [[ "$(stat -c %Y "$IMPL_BITSTREAM")" -gt "$(stat -c %Y "$BITSTREAM")" ]]; then
    mkdir -p "$(dirname "$BITSTREAM")"
    cp -f "$IMPL_BITSTREAM" "$BITSTREAM"
  fi
fi

mkdir -p "$LOG_DIR" "$ARCHIVE_DIR" "$(dirname "$RESULTS")"

echo "=== HDC Phase 3 EMG replay (hdc_emg_board_test.c) ==="

if [[ ! -f "$EMG_HEADER" ]]; then
  echo "EMG vectors missing — running prep_emg_board_test.sh..."
  ( cd "$REPO" && bash scripts/prep_emg_board_test.sh )
fi

if [[ ! -f "$EMG_ELF" ]]; then
  echo "EMG ELF missing — running build_sw.sh..."
  ( cd "$ROOT" && bash build_sw.sh )
fi

for f in "$BITSTREAM" "$PS7_INIT" "$FSBL" "$EMG_ELF"; do
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

echo "=== Program + poll Phase 3 EMG replay ==="
set +e
hdc_xsdb "$ROOT/_ide/run_emg_all.tcl" | tee "$LOG_DIR/run_phase3_emg.log"
XSDB_RC=${PIPESTATUS[0]}
set -e

if ! grep -qE "EMG replay: N=[0-9]+ correct=[0-9]+ accuracy=" "$LOG_DIR/run_phase3_emg.log"; then
  echo "ERROR: EMG replay output missing expected summary line" >&2
  exit 1
fi

PASS_LINE="$(grep -E "Board vs export:.*PASS \(0.5% tol\)|Board vs export:.*FAIL \(0.5% tol\)" "$LOG_DIR/run_phase3_emg.log" | tail -1 || true)"
EMG_LINE="$(grep -E "^EMG replay:" "$LOG_DIR/run_phase3_emg.log" | tail -1 || true)"
REF_LINE="$(grep -E "^Export ref:" "$LOG_DIR/run_phase3_emg.log" | tail -1 || true)"
BOARD_LINE="$(grep -E "^Board vs export:" "$LOG_DIR/run_phase3_emg.log" | tail -1 || true)"
INFO_LINE="$(grep -E "^INFO frozen baseline" "$LOG_DIR/run_phase3_emg.log" | tail -1 || true)"

{
  echo "Phase 3 — EMG full-dataset replay (ZedBoard)"
  echo "============================================"
  echo "Date:       $(date -Iseconds)"
  echo "App:        sw/hdc_emg_board_test.c"
  echo "Method:     JTAG readback @ 0x00100300"
  echo "Run script: bash board/HDC_DMA/run_phase3_emg.sh"
  echo "Bitstream:  $BITSTREAM"
  echo ""
  grep -v "^$" "$LOG_DIR/run_phase3_emg.log" | sed -n '/^==================================================/,$p'
  echo ""
  echo "Record"
  echo "------"
  echo "Windows replayed: ${EMG_LINE#EMG replay: N=}"
  [[ -n "$REF_LINE" ]] && echo "$REF_LINE"
  [[ -n "$BOARD_LINE" ]] && echo "$BOARD_LINE"
  [[ -n "$INFO_LINE" ]] && echo "$INFO_LINE"
  if [[ "$PASS_LINE" == *PASS* ]]; then
    echo "PASS (board vs export, 0.5%): yes"
    echo ""
    echo "Status: PASS"
  else
    echo "PASS (board vs export, 0.5%): no"
    echo ""
    echo "Status: FAIL (board vs export ref; see v1/v2 criteria in README)"
  fi
} >"$RESULTS"

cp -f "$LOG_DIR/run_phase3_emg.log" "$ARCHIVE_DIR/board_emg_replay_run.log"

echo "Results saved: $RESULTS"
grep -E "EMG replay:|Export ref:|Board vs export:|INFO frozen" "$RESULTS" || true

if [[ "$PASS_LINE" == *PASS* ]]; then
  echo "SUCCESS: Phase 3 EMG replay complete (board within 0.5% of export ref)."
  exit 0
fi

echo "DONE: Phase 3 EMG replay ran; board outside 0.5% of export ref tolerance."
exit "$XSDB_RC"
