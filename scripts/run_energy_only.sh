#!/usr/bin/env bash
# Energy campaign only — stops for human review before push / anchors / golden regen.
#
# Usage:
#   bash scripts/run_energy_only.sh          # full campaign A→ARM
#   bash scripts/run_energy_campaign_resume.sh   # resume partial (A run02+)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/results/phase3/energy_runs/energy_only.log"
PAUSE_FILE="$ROOT/results/phase3/energy_runs/PAUSE_FOR_REVIEW"

exec > >(tee -a "$LOG") 2>&1

echo "=== Energy-only workflow $(date -Iseconds) ==="

if [[ -f "$ROOT/results/phase3/energy_runs/campaign_resume.log" ]] \
   && [[ -f "$ROOT/results/phase3/energy_runs/anchor_B/run03/energy_batch.txt" ]] \
   && [[ ! -f "$ROOT/results/phase3/energy_runs/anchor_C/run03/energy_batch.txt" ]]; then
  echo "Resuming from anchor C (A+B already complete)..."
  bash "$ROOT/scripts/run_energy_campaign_from_C.sh"
else
  bash "$ROOT/scripts/run_energy_campaign.sh"
fi

python3 "$ROOT/scripts/aggregate_energy_runs.py" --write-summary

cat > "$PAUSE_FILE" <<EOF
Energy campaign finished: $(date -Iseconds)

Review:
  results/phase3/energy_summary.txt
  results/phase3/energy_runs/anchor_*/README.md

When ready for the rest (golden_expect regen, git push, overnight EMG anchors):
  bash scripts/run_after_energy_review.sh

Logs:
  results/phase3/energy_runs/energy_only.log
  results/phase3/energy_runs/campaign_resume.log
EOF

echo ""
echo "=============================================="
echo " PAUSED — energy complete; review before next step"
echo " See: results/phase3/energy_runs/PAUSE_FOR_REVIEW"
echo "=============================================="
