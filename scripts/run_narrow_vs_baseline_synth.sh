#!/usr/bin/env bash
# #29 step 6: OOC baseline vs narrow synthesis + CSV summary.
#
# Usage (from repo root):
#   bash scripts/run_narrow_vs_baseline_synth.sh
#
# Requires Vivado 2024.2 (sets /cad/Xilinx/Vivado/2024.2 if vivado not in PATH).

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v vivado >/dev/null 2>&1; then
  if [[ -x /cad/Xilinx/Vivado/2024.2/settings64.sh ]]; then
    # shellcheck disable=SC1091
    source /cad/Xilinx/Vivado/2024.2/settings64.sh
  fi
fi

if ! command -v vivado >/dev/null 2>&1; then
  echo "ERROR: vivado not found; source Vivado settings64.sh first" >&2
  exit 1
fi

python3 scripts/gen_sel_table.py --check

LOG="$ROOT/results/dsweep/narrow_vs_baseline_synth.log"
mkdir -p "$ROOT/results/dsweep"
echo "Logging to $LOG"
vivado -mode batch -notrace -source scripts/narrow_vs_baseline_synth.tcl \
  -log "$LOG" -journal "$ROOT/results/dsweep/narrow_vs_baseline_synth.jou"

echo ""
bash "$ROOT/scripts/compare_narrow_vs_baseline_lut.sh"
