#!/usr/bin/env bash
# Phase 1 local gate — run before any HDC-2 rerun or PR.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Probe by executing: Windows ships a python3 alias stub that resolves on PATH
# but cannot run.
PY=""
for candidate in python3 python py; do
  if "$candidate" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
[[ -n "$PY" ]] || { echo "no working python3/python interpreter on PATH" >&2; exit 1; }

echo "== HDC-2 split unit tests =="
"$PY" python_ref/tests/test_split_hdc2.py

echo "== Synthetic audit =="
"$PY" scripts/audit_split_leakage.py --synthetic-only

echo "== hdc_ref smoke =="
(cd python_ref && "$PY" run_smoke_test.py)

if [[ -f python_ref/HDC-EMG/dataset.mat ]]; then
  echo "== HDC-2 dataset gate =="
  "$PY" scripts/audit_split_leakage.py \
    --config python_ref/config/emg_baseline_v2.json
else
  echo "SKIP dataset gate (clone python_ref/HDC-EMG for full audit)"
fi

echo "== HDC-2 gate script OK =="
