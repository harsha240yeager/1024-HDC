#!/usr/bin/env bash
# Stage B Twist 1 keep grid (issue #21): informed vs random @ keep ∈ {0.125, 0.25, 0.5}.
#
# Usage (from repo root):
#   bash scripts/run_twist1_stage_b_keep_grid.sh
#   bash scripts/run_twist1_stage_b_keep_grid.sh --quick
#   bash scripts/run_twist1_stage_b_keep_grid.sh --keep 0.25
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
QUICK=0
ONLY_KEEP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --keep)
      ONLY_KEEP="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

declare -A KEEP_DIRS=(
  [0.125]="twist1_stage_b_keep0125"
  [0.25]="twist1_stage_b_keep0250"
  [0.5]="twist1_stage_b_keep0500"
)

run_one() {
  local keep="$1"
  local dir="${KEEP_DIRS[$keep]}"
  local out="$REPO/results/protocol_v2/$dir"
  mkdir -p "$out"
  echo "=== Stage B Twist 1 keep=$keep -> $out ==="
  local extra=()
  if [[ "$QUICK" -eq 1 ]]; then
    extra+=(--quick)
  fi
  python3 "$REPO/python_ref/run_twist1_stage_b_sweep.py" \
    --keep "$keep" \
    --out-dir "$out" \
    "${extra[@]}" \
    2>&1 | tee "$out/full_sweep.log"
  python3 "$REPO/python_ref/tools/subject_level_stats.py" \
    --results "$out/twist1_results.json"
}

if [[ -n "$ONLY_KEEP" ]]; then
  run_one "$ONLY_KEEP"
else
  for keep in 0.125 0.25 0.5; do
    run_one "$keep"
  done
fi

echo "Done. Index: results/protocol_v2/twist1_stage_b/README.md"
