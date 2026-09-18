#!/usr/bin/env bash
# Issue #39 — Antonio identical-across-prototypes baseline (HDC-2).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 python_ref/run_antonio_compact_baseline.py "$@"
