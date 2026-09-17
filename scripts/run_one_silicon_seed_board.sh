#!/usr/bin/env bash
# One Twist-1 silicon random seed: patch mask, set export ref, JTAG EMG replay.
# Usage: bash scripts/run_one_silicon_seed_board.sh 3
set -euo pipefail

SEED="${1:?seed number required}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/results/protocol_v2/twist1_silicon"
PRED="$OUT/random_seed_${SEED}/prediction.json"
DMA="$ROOT/board/HDC_DMA"

if [[ ! -f "$PRED" ]]; then
  echo "Missing $PRED — run: bash scripts/run_silicon_random_seeds.sh --seeds $SEED" >&2
  exit 1
fi

REF_X1000="$(python3 - <<PY
import json
p = json.load(open("$PRED"))
print(int(round(p["export_ref_accuracy_pct"] * 1000)))
PY
)"

echo "=== Seed $SEED (export ref x1000=$REF_X1000) ==="
python3 "$ROOT/scripts/patch_emg_anchor.py" \
  --anchor C --keep-ratio 0.125 \
  --mask-mode random --random-seed "$SEED" \
  --label "twist1_random_s${SEED}" --skip-accuracy

python3 - <<PY
import re
from pathlib import Path
for path in [
    Path("$ROOT/sw/emg_board_vectors.h"),
    Path("$ROOT/sw/emg_board_vectors_hdc2.h"),
]:
    text = path.read_text()
    text = re.sub(
        r"#define EMG_EXPORT_REF_ACCURACY_X1000\s+\d+U",
        f"#define EMG_EXPORT_REF_ACCURACY_X1000   ${REF_X1000}U",
        text,
        count=1,
    )
    path.write_text(text)
print("Set EMG_EXPORT_REF_ACCURACY_X1000 =", ${REF_X1000})
PY

unset HDC_NARROW HDC_VIVADO_ROOT
export HDC_EMG_RESULTS="$OUT/random_seed_${SEED}/board_emg_replay.txt"
export HDC_EMG_RESULTS_DIR="$OUT/random_seed_${SEED}"
export HDC_LOG_DIR="/tmp/hdc_seed${SEED}_$(date +%Y%m%d_%H%M)"
export HDC_ANCHOR_SKIP_PATCH=1
mkdir -p "$HDC_LOG_DIR"

# shellcheck source=/dev/null
source "$DMA/_ide/common.sh"
hdc_stop_conflicting_sessions || true
hdc_stop_hw_server || true
sleep 2
hdc_start_hw_server || exit 1
sleep 2
hdc_wait_for_digilent_usb 30 || exit 1

bash "$DMA/run_anchor_replay.sh" C 2>&1 | tee "$HDC_LOG_DIR/run.log"

python3 "$ROOT/scripts/merge_measured_silicon_seeds.py"
grep -E "EMG replay:|Board vs export:|Status:" "$HDC_EMG_RESULTS" || true
