#!/usr/bin/env bash
# Prepare ARM HDC bench headers (item mem + golden vectors, same seed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GOLDEN_SEED="${GOLDEN_SEED:-42}"
VECDIR="$ROOT/python_ref/vectors/cosim_core"
OUTH="$ROOT/sw/arm_bench_data.h"

GOLDEN_SEED="$GOLDEN_SEED" bash "$ROOT/scripts/prep_golden_test.sh"

echo "Exporting arm_bench_data.h from $VECDIR (must match golden_vectors.h)..."
python3 "$ROOT/python_ref/tools/export_arm_bench_data.py" "$VECDIR" "$OUTH"

echo "Ready:"
echo "  sw/hdc_arm_bench.c"
echo "  sw/hdc_arm_ref.c"
echo "  sw/arm_bench_data.h"
echo "  sw/golden_vectors.h"
