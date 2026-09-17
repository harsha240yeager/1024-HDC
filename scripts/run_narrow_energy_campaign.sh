#!/usr/bin/env bash
# INA219 energy: narrow PL @ anchor C (K=128, keep=0.125), n=3 runs — issue #31.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="$ROOT/board/HDC_DMA"
LOG="$ROOT/results/protocol_v2/narrow_rtl/energy_runs/campaign.log"
NARROW_BENCH="bash $BOARD/run_narrow_phase3_bench_load_energy.sh"
BASE="$ROOT/results/protocol_v2/narrow_rtl/energy_runs/anchor_C"

mkdir -p "$BASE"
exec > >(tee -a "$LOG") 2>&1

echo "=== Narrow energy campaign $(date -Iseconds) ==="

python3 "$ROOT/scripts/patch_emg_anchor.py" --anchor C --skip-accuracy

patch_anchor() { python3 "$ROOT/scripts/patch_emg_anchor.py" --anchor C --skip-accuracy; }

for run in 01 02 03; do
  echo "=== narrow anchor C run ${run}/3 ==="
  patch_anchor
  ENERGY_RUN_DIR="$BASE/run${run}" \
    ENERGY_BENCH_CMD="$NARROW_BENCH" \
    ENERGY_BATCH_MS="0.558" \
    ENERGY_BATCH_WINDOWS=200 \
    ENERGY_ANCHOR="C" \
    ENERGY_BENCH_MS_FILE="/tmp/hdc_narrow_bench_load_energy/batch_ms.txt" \
    bash "$ROOT/scripts/run_energy_one_run.sh"
done

python3 "$ROOT/scripts/aggregate_energy_runs.py" \
  --runs-root "$ROOT/results/protocol_v2/narrow_rtl/energy_runs" \
  --write-narrow-summary

python3 "$ROOT/scripts/gen_narrow_board_eval_summary.py"

echo "SUCCESS: narrow energy campaign complete."
