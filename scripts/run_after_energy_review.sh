#!/usr/bin/env bash
# After energy review: golden_expect regen, git push, overnight EMG anchors.
#
# Usage: bash scripts/run_after_energy_review.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/results/phase3/post_energy.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== Post-energy workflow $(date -Iseconds) ==="

if [[ ! -f "$ROOT/results/phase3/energy_summary.txt" ]]; then
  echo "ERROR: energy_summary.txt missing — finish energy campaign first" >&2
  exit 1
fi

echo "== Regenerate golden_expect for anchors A/B/C (bench golden PASS) =="
for id in A B C; do
  python3 "$ROOT/scripts/regenerate_golden_expect.py" --anchor "$id" || {
    echo "WARNING: golden_expect regen for $id failed (continuing)" >&2
  }
done

echo "== Git commit + push =="
cd "$ROOT"
git add scripts/ board/HDC_DMA/ results/phase3/energy_runs/ results/phase3/energy_summary.txt \
  sw/golden_vectors.h sw/emg_board_vectors.h 2>/dev/null || true

if ! git diff --staged --quiet; then
  git commit -m "$(cat <<'EOF'
Record self-consistent INA219 energy at anchors A/B/C and ARM path.

Pooled Fisher mask in golden + emg headers; energy_summary and per-anchor runs.
EOF
)"
  git push origin main
else
  echo "Nothing new to commit"
fi

echo "== Overnight EMG anchor replays (A/B/C) =="
mkdir -p "$ROOT/results/protocol_v2/anchors"
nohup bash "$ROOT/board/HDC_DMA/run_anchor_replay.sh" ALL \
  >> "$ROOT/results/protocol_v2/anchors/overnight.log" 2>&1 &
echo "Anchors PID=$! log=results/protocol_v2/anchors/overnight.log"

rm -f "$ROOT/results/phase3/energy_runs/PAUSE_FOR_REVIEW"
echo "=== Post-energy workflow launched $(date -Iseconds) ==="
