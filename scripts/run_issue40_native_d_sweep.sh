#!/usr/bin/env bash
# Issue #40 — native D=128/256 vs K=128 gather (HDC-2).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 python_ref/run_native_d_sweep.py "$@"
