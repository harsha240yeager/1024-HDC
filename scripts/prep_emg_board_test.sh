#!/usr/bin/env bash
# Export EMG board vectors header v2 (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DATASET="$ROOT/python_ref/HDC-EMG/dataset.mat"
if [[ ! -f "$DATASET" ]]; then
  echo "EMG dataset missing. Cloning HDC-EMG..."
  ( cd python_ref && git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG )
fi

ENGINE="${EMG_ENGINE:-hdc_ref}"
MAX_WIN="${EMG_MAX_WINDOWS:-}"

ARGS=(--engine "$ENGINE" --out "$ROOT/sw/emg_board_vectors.h")
if [[ -n "$MAX_WIN" ]]; then
  ARGS+=(--max-windows "$MAX_WIN")
fi

python3 "$ROOT/scripts/export_emg_board_vectors.py" "${ARGS[@]}"

echo ""
echo "Ready. Board app sources:"
echo "  sw/hdc_emg_board_test.c"
echo "  sw/hdc_dma_stream.c"
echo "  sw/hdc_core_regs.c"
echo "  sw/emg_board_vectors.h"
