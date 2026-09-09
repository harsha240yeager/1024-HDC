#!/usr/bin/env bash
# One-shot JTAG readback of EMG replay results @ 0x00100300 — no reprogram, no poll loop.
#
# Use when run_emg_all.tcl poll errors but the board may have finished (or is still running).
# If status != done, exit 2 (still running). If done, writes board_emg_replay.txt.
#
# Usage:
#   bash board/HDC_DMA/fetch_emg_results.sh
#   HDC_EMG_RESULTS=/path/to/board_emg_replay.txt bash board/HDC_DMA/fetch_emg_results.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_fetch_emg}"
RESULTS="${HDC_EMG_RESULTS:-$REPO/results/protocol_v2/narrow_rtl/anchors/anchor_C/board_emg_replay.txt}"

# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"

mkdir -p "$LOG_DIR" "$(dirname "$RESULTS")"

hdc_stop_conflicting_sessions || exit 1
hdc_source_tools
hdc_ensure_hw_server
sleep 1

if ! lsusb | grep -q '0403:6014'; then
  echo "ERROR: Digilent USB not found (0403:6014)" >&2
  exit 1
fi

echo "=== One-shot EMG result fetch (no reprogram) ==="
set +e
hdc_xsdb "$ROOT/_ide/poll_emg_status.tcl" 2>&1 | tee "$LOG_DIR/fetch_emg.log"
RC=${PIPESTATUS[0]}
set -e

if grep -q "RUNNING or stale" "$LOG_DIR/fetch_emg.log"; then
  grep -E "magic=|status=|n=|correct=" "$LOG_DIR/fetch_emg.log" || true
  echo "Still running — retry later or watch UART on /dev/ttyUSB0 @ 115200"
  exit 2
fi

if ! grep -qE "EMG replay: N=" "$LOG_DIR/fetch_emg.log"; then
  echo "ERROR: could not read results — see $LOG_DIR/fetch_emg.log" >&2
  exit "$RC"
fi

{
  echo "Phase 3 — EMG replay result fetch (one-shot JTAG, no reprogram)"
  echo "Date: $(date -Iseconds)"
  echo ""
  grep -v "^$" "$LOG_DIR/fetch_emg.log" | sed -n '/^==================================================/,$p'
  echo ""
  if grep -q "PASS (0.5% tol)" "$LOG_DIR/fetch_emg.log"; then
    echo "Status: PASS"
  else
    echo "Status: FAIL"
  fi
} >"$RESULTS"

echo "Saved: $RESULTS"
grep -E "EMG replay:|Export ref:|Board vs export:|Status:" "$RESULTS" || true
exit "$RC"
