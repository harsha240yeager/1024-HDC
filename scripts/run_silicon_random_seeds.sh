#!/usr/bin/env bash
# Issue #26 / #27 — Twist-1 silicon random-mask seeds (predict + optional board).
#
# Default: Python export-ref prediction (seed 0 validated Δ0.00 pp vs board).
# With --board: patch mask + JTAG replay on ZedBoard (requires hardware).
#
# Usage:
#   bash scripts/run_silicon_random_seeds.sh
#   bash scripts/run_silicon_random_seeds.sh --seeds 1-9
#   bash scripts/run_silicon_random_seeds.sh --board --seeds 1-9 --resume
#   bash scripts/run_silicon_random_seeds.sh --quick   # 5k windows dev test
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/results/protocol_v2/twist1_silicon"
SEEDS="0-9"
RUN_BOARD=0
RESUME=0
QUICK=0
KEEP="0.125"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seeds) SEEDS="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --keep) KEEP="$2"; shift 2 ;;
    --board) RUN_BOARD=1; shift ;;
    --resume) RESUME=1; shift ;;
    --quick) QUICK=1; shift ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

expand_seeds() {
  local spec="$1" out=()
  if [[ "$spec" == *-* ]]; then
    local a="${spec%-*}" b="${spec#*-}"
    for ((i=a; i<=b; i++)); do out+=("$i"); done
  else
    IFS=',' read -ra out <<< "$spec"
  fi
  printf '%s\n' "${out[@]}"
}

PY=""
for candidate in python3 python py; do
  if "$candidate" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
[[ -n "$PY" ]] || { echo "no python interpreter" >&2; exit 1; }

PRED_ARGS=(--out-dir "$OUT_DIR")
QUICK_ARGS=()
if [[ "$QUICK" -eq 1 ]]; then
  QUICK_ARGS=(--max-windows 5000)
  echo "QUICK: 5000 windows only"
fi

mapfile -t SEED_LIST < <(expand_seeds "$SEEDS")
PRED_ARGS+=(--seeds "${SEED_LIST[@]}")

echo "=== Python silicon prediction (issue #26) ==="
"$PY" "$ROOT/python_ref/predict_twist1_silicon_seeds.py" "${PRED_ARGS[@]}" "${QUICK_ARGS[@]}"

if [[ "$RUN_BOARD" -eq 0 ]]; then
  echo "Prediction complete. Board replay skipped (pass --board when ZedBoard ready)."
  exit 0
fi

echo ""
echo "=== Board replay (ZedBoard required) ==="
BOARD_SEEDS=""
for seed in "${SEED_LIST[@]}"; do
  seed="$(echo "$seed" | tr -d ' ')"
  replay="$OUT_DIR/random_seed_${seed}/board_emg_replay.txt"
  if [[ "$RESUME" -eq 1 && -f "$replay" ]]; then
    echo "SKIP seed $seed (existing $replay)"
    continue
  fi
  BOARD_SEEDS="${BOARD_SEEDS:+$BOARD_SEEDS,}$seed"
done

if [[ -z "$BOARD_SEEDS" ]]; then
  echo "All requested seeds already have board_emg_replay.txt"
else
  bash "$ROOT/board/HDC_DMA/run_twist1_board.sh" \
    --keep "$KEEP" --random-seeds "$BOARD_SEEDS"
fi

echo "=== Refresh summary with board measurements ==="
"$PY" "$ROOT/python_ref/predict_twist1_silicon_seeds.py" "${PRED_ARGS[@]}"

echo "Done -> $OUT_DIR/seed_summary.json"
