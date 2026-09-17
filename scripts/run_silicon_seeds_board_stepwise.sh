#!/usr/bin/env bash
# Run board EMG replay for seeds sequentially (3–9 default), merge summary after each.
#
# Usage:
#   bash scripts/run_silicon_seeds_board_stepwise.sh
#   bash scripts/run_silicon_seeds_board_stepwise.sh 3 4 5
#   bash scripts/run_silicon_seeds_board_stepwise.sh --from 5
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/results/protocol_v2/twist1_silicon"
LOG="$OUT/board_stepwise.log"
FROM=3
SEEDS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *) SEEDS+=("$1"); shift ;;
  esac
done

if [[ ${#SEEDS[@]} -eq 0 ]]; then
  for ((s=FROM; s<=9; s++)); do SEEDS+=("$s"); done
fi

mkdir -p "$OUT"
exec > >(tee -a "$LOG") 2>&1

echo "=== Silicon board stepwise campaign $(date -Iseconds) ==="
echo "Seeds: ${SEEDS[*]}"

for seed in "${SEEDS[@]}"; do
  replay="$OUT/random_seed_${seed}/board_emg_replay.txt"
  if [[ -f "$replay" ]] && grep -q "Status: PASS" "$replay" 2>/dev/null; then
    echo "SKIP seed $seed (existing PASS $replay)"
    continue
  fi
  echo ""
  echo "########## SEED $seed START $(date -Iseconds) ##########"
  if bash "$ROOT/scripts/run_one_silicon_seed_board.sh" "$seed"; then
    echo "########## SEED $seed END OK $(date -Iseconds) ##########"
  else
    echo "########## SEED $seed END FAILED (continuing) $(date -Iseconds) ##########"
  fi
done

python3 "$ROOT/scripts/merge_measured_silicon_seeds.py"
echo "Campaign complete -> $OUT/seed_summary.json"
