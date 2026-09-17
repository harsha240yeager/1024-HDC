#!/usr/bin/env bash
# Issue #32 — refresh util CSV, Pareto data CSV, and figures.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash scripts/compare_narrow_vs_baseline_lut.sh
python3 scripts/generate_narrow_pareto_csv.py
python3 python_ref/plot_narrow_pareto.py --paper --dpi 300
