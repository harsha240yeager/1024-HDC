#!/usr/bin/env bash
# Twist 2 @ 36 UCI subjects under Protocol HDC-2 — keep-ratio stress grid (issue #2).
#
# Bits @ D=1024: 32, 64, 96, 128, 192, 256
# With a shared encode cache, only the Fisher/eval phase reruns per keep point (~2–4 h each).
# Full encode from scratch: ~8 h once (see ENCODE_CACHE_SRC).
#
# Usage (from repo root, after dataset_36.mat exists):
#   bash scripts/run_twist2_36_v2_keep_grid.sh
#   bash scripts/run_twist2_36_v2_keep_grid.sh --quick
#   bash scripts/run_twist2_36_v2_keep_grid.sh --keep-bits 64
#   bash scripts/run_twist2_36_v2_keep_grid.sh --out-root results/repro/full/twist2_36_v2
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$REPO/python_ref/config/twist2_36_v2_sweep.json"
EMG_CFG="$REPO/python_ref/config/emg_baseline_v2.json"
OUT_ROOT="$REPO/results/protocol_v2/twist2_36_v2"
ENCODE_CACHE_SRC="${ENCODE_CACHE_SRC:-$REPO/results/protocol_v2/twist2_36_v2_keep128/encode_cache}"
PRIMARY_KEEP128="$REPO/results/protocol_v2/twist2_36_v2_keep128"
QUICK=0
ONLY_BITS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --keep-bits)
      ONLY_BITS="$2"
      shift 2
      ;;
    --out-root)
      case "$2" in
        /*) OUT_ROOT="$2" ;;
        *) OUT_ROOT="$REPO/$2" ;;
      esac
      shift 2
      ;;
    -h|--help)
      sed -n '2,14p' "$0"
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

encode_cache_ready() {
  [[ -d "$ENCODE_CACHE_SRC" ]] || return 1
  [[ -f "$ENCODE_CACHE_SRC/manifest.json" ]] || return 1
  [[ "$(find "$ENCODE_CACHE_SRC" -maxdepth 1 -name 's*.npz' | wc -l)" -eq 36 ]]
}

link_encode_cache() {
  local out="$1"
  mkdir -p "$out"
  if [[ -e "$out/encode_cache" && ! -L "$out/encode_cache" ]]; then
    echo "  encode_cache exists and is not a symlink — leave in place" >&2
    return 0
  fi
  ln -sfn "$ENCODE_CACHE_SRC" "$out/encode_cache"
}

publish_primary_keep128() {
  local out="$1"
  mkdir -p "$out"
  for f in twist2_results.json twist2_summary.csv README.md twist2_results.partial.json; do
    if [[ -f "$PRIMARY_KEEP128/$f" && ! -f "$out/$f" ]]; then
      cp -a "$PRIMARY_KEEP128/$f" "$out/$f"
    fi
  done
  if [[ -f "$PRIMARY_KEEP128/full_run.log" && ! -f "$out/full_sweep.log" ]]; then
    cp -a "$PRIMARY_KEEP128/full_run.log" "$out/full_sweep.log"
  fi
  link_encode_cache "$out"
}

mkdir -p "$OUT_ROOT"

for bits in "${KEEP_BITS[@]}"; do
  keep="$(python3 -c "print(${bits}/1024)")"
  out="$OUT_ROOT/keep_${bits}"
  mkdir -p "$out"

  if [[ -f "$out/twist2_results.json" ]]; then
    echo "=== SKIP keep=${bits} bits — twist2_results.json exists ==="
    continue
  fi

  if [[ "$bits" -eq 128 && -f "$PRIMARY_KEEP128/twist2_results.json" ]]; then
    echo "=== keep=${bits} bits — publishing primary run from $PRIMARY_KEEP128 ==="
    publish_primary_keep128 "$out"
    continue
  fi

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
  elif encode_cache_ready; then
    echo "  shared encode cache ready — evaluate-only"
    link_encode_cache "$out"
    args+=(--evaluate-only)
  else
    echo "  no full encode cache — full encode + eval (--resume)"
    args+=(--resume)
  fi

  "${args[@]}" 2>&1 | tee "$out/full_sweep.log"
done

echo "Grid complete under $OUT_ROOT"
