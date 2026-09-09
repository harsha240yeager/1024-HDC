#!/usr/bin/env bash
# Wait for narrow EMG replay, then one-shot fetch (no poll loop).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS="$REPO/results/protocol_v2/narrow_rtl/anchors/anchor_C/board_emg_replay.txt"
LOG="${HDC_MONITOR_LOG:-/tmp/narrow_emg_monitor.log}"
FETCH="$REPO/board/HDC_DMA/fetch_emg_results.sh"

exec >>"$LOG" 2>&1
echo "=== monitor start $(date -Iseconds) ==="

while pgrep -f 'run_emg_all.tcl' >/dev/null 2>&1; do
  echo "$(date +%H:%M:%S) xsdb poll still running..."
  sleep 120
done
echo "$(date +%H:%M:%S) xsdb poll exited"

if [[ -f "$RESULTS" ]] && grep -q "EMG replay:" "$RESULTS"; then
  echo "Results already present"
  exit 0
fi

deadline=$(( $(date +%s) + 10800 ))
while [[ $(date +%s) -lt $deadline ]]; do
  pkill -f 'run_emg_all.tcl' 2>/dev/null || true
  sleep 5
  set +e
  HDC_EMG_RESULTS="$RESULTS" bash "$FETCH"
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    echo "=== DONE $(date -Iseconds) ==="
    exit 0
  fi
  echo "$(date +%H:%M:%S) fetch rc=$rc (2=still running) — sleep 10m"
  sleep 600
done
exit 1
