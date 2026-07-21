#!/usr/bin/env bash
# Twist 2 @ 36 UCI subjects under Protocol HDC-2 — keep-ratio stress grid (issue #2).
#
# Bits @ D=1024: 32, 64, 96, 128, 192, 256
# Runtime: ~17 h per keep point (similar to HDC-1 36-subject runs).
#
# Usage (from repo root, after dataset_36.mat exists):
#   bash scripts/run_twist2_36_v2_keep_grid.sh
#   bash scripts/run_twist2_36_v2_keep_grid.sh --quick
#   bash scripts/run_twist2_36_v2_keep_grid.sh --keep-bits 128
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$REPO/python_ref/config/twist2_36_v2_sweep.json"
EMG_CFG="$REPO/python_ref/config/emg_baseline_v2.json"
OUT_ROOT="$REPO/results/protocol_v2/twist2_36_v2"
QUICK=0
ONLY_BITS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --keep-bits)
      ONLY_BITS="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

DATASET="$REPO/python_ref/HDC-EMG/dataset_36.mat"
if [[ ! -f "$DATASET" ]]; then
  echo "Missing $DATASET — run: python3 scripts/build_uci_emg_dataset.py" >&2
  exit 1
fi

KEEP_BITS=(32 64 96 128 192 256)
if [[ -n "$ONLY_BITS" ]]; then
  KEEP_BITS=("$ONLY_BITS")
fi

mkdir -p "$OUT_ROOT"

for bits in "${KEEP_BITS[@]}"; do
  keep="$(python3 -c "print(${bits}/1024)")"
  out="$OUT_ROOT/keep_${bits}"
  mkdir -p "$out"
  echo "=== Twist 2 36-subj HDC-2 keep=${bits} bits (ratio=${keep}) ==="
  args=(
    python3 "$REPO/python_ref/run_twist2_sweep.py"
    --config "$CFG"
    --emg-config "$EMG_CFG"
    --keep "$keep"
    --out-dir "$out"
  )
  if [[ "$QUICK" -eq 1 ]]; then
    args+=(--quick)
  fi
  "${args[@]}" 2>&1 | tee "$out/full_sweep.log"
done

echo "Grid complete under $OUT_ROOT"
