#!/usr/bin/env bash
# Pack HDC-2 export header for Zynq EMG replay (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FULL="$ROOT/sw/emg_board_vectors_hdc2.h"
if [[ ! -f "$FULL" ]]; then
  echo "Missing $FULL — run export first:" >&2
  echo "  python3 scripts/export_emg_board_vectors.py --config python_ref/config/emg_baseline_v2.json --out $FULL" >&2
  exit 1
fi

echo "== Pack HDC-2 EMG vectors (DDR bin + slim header) =="
python3 "$ROOT/scripts/pack_emg_ddr_from_header.py" \
  --header "$FULL" \
  --bin "$ROOT/sw/emg_board_vectors.bin" \
  --out-header "$ROOT/sw/emg_board_vectors.h"

echo ""
echo "Ready for board replay (Protocol HDC-2):"
echo "  sw/emg_board_vectors.h      (slim, protos+mask)"
echo "  sw/emg_board_vectors.bin    (493512 windows @ DDR 0x02000000)"
echo "  cd board/HDC_DMA && bash build_sw.sh && bash run_phase3_emg.sh"
