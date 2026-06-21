#!/usr/bin/env bash
# Prepare golden-vector header for Zynq bare-metal build (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VECDIR="$ROOT/python_ref/vectors/cosim_core"
OUTH="$ROOT/sw/golden_vectors.h"

if [[ ! -f "$VECDIR/core_expect.hex" ]]; then
  echo "Generating core vectors (seed 42, 200 cases)..."
  (cd "$ROOT/python_ref" && python generate_vectors.py --core --out-dir vectors/cosim_core --count 200 --seed 42)
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
