#!/usr/bin/env bash
# Issue #9 — Fisher vs ranking baselines @ keep=128 (HDC-2, hdc_ref encoder).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${1:-/tmp/issue9_ranking_baselines.log}"
echo "=== Issue #9 ranking baselines $(date -Iseconds) ===" | tee "$LOG"
python3 python_ref/run_ranking_baselines.py 2>&1 | tee -a "$LOG"
echo "Done. Artifacts: results/protocol_v2/ranking_baselines/" | tee -a "$LOG"
