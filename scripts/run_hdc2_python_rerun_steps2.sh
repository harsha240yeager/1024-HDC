#!/usr/bin/env bash
# Resume HDC-2 Tier 1 from step 2 (after baseline JSON exists).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V2_CFG="$ROOT/python_ref/config/emg_baseline_v2.json"
OUT="$ROOT/results/protocol_v2"
HDR="$ROOT/sw/emg_board_vectors_hdc2.h"
LOG="$OUT/rerun.log"

mkdir -p "$OUT"
exec >>"$LOG" 2>&1

echo "=== HDC-2 resume steps 2–5 $(date -Iseconds) ==="

cp "$ROOT/python_ref/results/emg_baseline.json" "$OUT/emg_baseline.json"

cd "$ROOT"

echo "== 2/5 export_emg_board_vectors.py =="
python3 scripts/export_emg_board_vectors.py --config "$V2_CFG" --out "$HDR"

echo "== 3/5 regenerate_emg_protos.py =="
python3 scripts/regenerate_emg_protos.py \
  --config "$V2_CFG" --header "$HDR" --slim-header "$HDR"

echo "== 4/5 export_fisher_pooled.py =="
python3 scripts/export_fisher_pooled.py \
  --config "$V2_CFG" --out "$OUT/fisher_pooled.npz"

echo "== 5/5 run_arm_hdc_baseline.py =="
python3 python_ref/run_arm_hdc_baseline.py \
  --emg-config "$V2_CFG" --out-dir "$OUT/arm_baseline"

echo "=== HDC-2 steps 2–5 COMPLETE $(date -Iseconds) ==="
