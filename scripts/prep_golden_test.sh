#!/usr/bin/env bash
# Prepare golden-vector header for Zynq bare-metal build (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VECDIR="$ROOT/python_ref/vectors/cosim_core"
OUTH="$ROOT/sw/golden_vectors.h"
GOLDEN_SEED="${GOLDEN_SEED:-42}"
GOLDEN_COUNT="${GOLDEN_COUNT:-200}"

need_regen=0
if [[ ! -f "$VECDIR/core_expect.hex" ]]; then
  need_regen=1
elif [[ -f "$VECDIR/meta.txt" ]]; then
  current_seed="$(grep '^seed=' "$VECDIR/meta.txt" | cut -d= -f2 || true)"
  if [[ "$current_seed" != "$GOLDEN_SEED" ]]; then
    echo "cosim_core seed=$current_seed != required $GOLDEN_SEED — regenerating"
    need_regen=1
  fi
fi

if [[ "$need_regen" -eq 1 ]]; then
  echo "Generating core vectors (seed $GOLDEN_SEED, $GOLDEN_COUNT cases)..."
  (cd "$ROOT/python_ref" && python3 generate_vectors.py --core --out-dir vectors/cosim_core \
    --count "$GOLDEN_COUNT" --seed "$GOLDEN_SEED")
fi

echo "Exporting C header..."
python3 "$ROOT/python_ref/tools/export_golden_c.py" "$VECDIR" "$OUTH"

echo ""
echo "Ready. Vitis app sources:"
echo "  sw/hdc_core_golden_test.c  (200-case golden test)"
echo "  sw/hdc_core_bench.c       (Phase 1 latency bench)"
echo "  sw/hdc_dma_stream_bench.c (Phase 2 DMA latency bench)"
echo "  sw/hdc_core_regs.c"
echo "  sw/golden_vectors.h"
