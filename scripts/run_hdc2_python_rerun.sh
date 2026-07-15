#!/usr/bin/env bash
# Protocol HDC-2 — Tier 1 Python rerun (issue #1).
# Logs to results/protocol_v2/rerun.log
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V2_CFG="$ROOT/python_ref/config/emg_baseline_v2.json"
OUT="$ROOT/results/protocol_v2"
HDR="$ROOT/sw/emg_board_vectors_hdc2.h"
LOG="$OUT/rerun.log"

mkdir -p "$OUT"
exec >>"$LOG" 2>&1

echo "=== HDC-2 Python rerun $(date -Iseconds) ==="
echo "Config: $V2_CFG"
echo "Log:    $LOG"

cd "$ROOT"

echo "== Gate =="
bash scripts/run_hdc2_gate.sh

echo "== 1/5 run_emg_baseline.py =="
python3 python_ref/run_emg_baseline.py \
  --config "$V2_CFG" \
  --measure-rtl-ref \
  --no-parity
cp python_ref/results/emg_baseline.json "$OUT/emg_baseline.json"

echo "== 2/5 export_emg_board_vectors.py (full TEST export — hours) =="
python3 scripts/export_emg_board_vectors.py \
  --config "$V2_CFG" \
  --out "$HDR"

echo "== 3/5 regenerate_emg_protos.py (unlimited bundle protos) =="
python3 scripts/regenerate_emg_protos.py \
  --config "$V2_CFG" \
  --header "$HDR" \
  --slim-header "$HDR"

echo "== 4/5 export_fisher_pooled.py =="
python3 scripts/export_fisher_pooled.py \
  --config "$V2_CFG" \
  --out "$OUT/fisher_pooled.npz"

echo "== 5/5 run_arm_hdc_baseline.py =="
python3 python_ref/run_arm_hdc_baseline.py \
  --emg-config "$V2_CFG" \
  --out-dir "$OUT/arm_baseline"

echo "=== HDC-2 Tier 1 Python rerun COMPLETE $(date -Iseconds) ==="
echo "Board header: $HDR"
echo "Next: cd board/HDC_DMA && build_sw.sh && run_phase3_emg.sh (point at hdc2 header)"
