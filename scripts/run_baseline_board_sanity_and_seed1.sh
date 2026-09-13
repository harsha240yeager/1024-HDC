#!/usr/bin/env bash
# After baseline bitstream is staged: bench golden -> informed anchor C -> random seed 1.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DMA="$ROOT/board/HDC_DMA"

unset HDC_NARROW HDC_VIVADO_ROOT
export HDC_LOG_DIR="/tmp/hdc_baseline_sanity_$(date +%Y%m%d_%H%M)"
mkdir -p "$HDC_LOG_DIR"

# shellcheck source=/dev/null
source "$DMA/_ide/common.sh"
hdc_stop_conflicting_sessions || true
hdc_stop_hw_server && sleep 2
hdc_start_hw_server && sleep 2
hdc_wait_for_digilent_usb 30
hdc_xsdb "$DMA/_ide/jtag_diagnose.tcl" | tail -3

echo "=== Baseline DMA bench + golden (expect PASS) ==="
cd "$ROOT" && bash scripts/prep_golden_test.sh
cd "$DMA" && bash build_sw.sh
bash run_phase3_bench.sh | tee "$HDC_LOG_DIR/bench.log"
grep -E "PASS:|FAIL:" "$HDC_LOG_DIR/bench.log" | tail -4

echo "=== Informed anchor C EMG sanity (~72.85%) ==="
python3 "$ROOT/scripts/patch_emg_anchor.py" --anchor C --keep-ratio 0.125 --mask-mode informed
export HDC_EMG_RESULTS="$ROOT/results/protocol_v2/anchors/anchor_C/board_emg_replay_sanity.txt"
export HDC_EMG_RESULTS_DIR="$ROOT/results/protocol_v2/anchors/anchor_C"
export HDC_LOG_DIR="/tmp/hdc_anchor_c_sanity_$(date +%Y%m%d_%H%M)"
bash run_anchor_replay.sh C | tee "$HDC_LOG_DIR/anchor_c.log"
grep -E "EMG replay:|Board vs export:|Status:" "$HDC_EMG_RESULTS" || true

echo "=== Random seed 1 board replay (~64.58%) ==="
python3 "$ROOT/scripts/patch_emg_anchor.py" --anchor C --keep-ratio 0.125 \
  --mask-mode random --random-seed 1 --label twist1_random_s1
export HDC_EMG_RESULTS="$ROOT/results/protocol_v2/twist1_silicon/random_seed_1/board_emg_replay.txt"
export HDC_EMG_RESULTS_DIR="$ROOT/results/protocol_v2/twist1_silicon/random_seed_1"
export HDC_LOG_DIR="/tmp/hdc_seed1_$(date +%Y%m%d_%H%M)"
export HDC_ANCHOR_SKIP_PATCH=1
bash run_anchor_replay.sh C | tee "$HDC_LOG_DIR/seed1.log"
grep -E "EMG replay:|Board vs export:|Status:" "$HDC_EMG_RESULTS" || true

echo "Done."
