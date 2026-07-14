#!/usr/bin/env bash
# Phase 1 local gate — run before any HDC-2 rerun or PR.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== HDC-2 split unit tests =="
python3 python_ref/tests/test_split_hdc2.py

echo "== Synthetic audit =="
python3 scripts/audit_split_leakage.py --synthetic-only

echo "== hdc_ref smoke =="
(cd python_ref && python3 run_smoke_test.py)

if [[ -f python_ref/HDC-EMG/dataset.mat ]]; then
  echo "== HDC-2 dataset gate =="
  python3 scripts/audit_split_leakage.py \
    --config python_ref/config/emg_baseline_v2.json
else
  echo "SKIP dataset gate (clone python_ref/HDC-EMG for full audit)"
fi

echo "== HDC-2 gate script OK =="
