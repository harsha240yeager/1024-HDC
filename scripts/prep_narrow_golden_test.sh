#!/usr/bin/env bash
# Prepare narrow golden-vector header for Zynq bare-metal bench (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VECDIR="$ROOT/python_ref/vectors/cosim_core_narrow"
OUTH="$ROOT/sw/golden_vectors_narrow.h"
GOLDEN_SEED="${GOLDEN_SEED:-42}"
GOLDEN_COUNT="${GOLDEN_COUNT:-200}"

echo "== Ensure anchor-C SEL package =="
python3 "$ROOT/scripts/gen_sel_table.py" --check

need_regen=0
if [[ ! -f "$VECDIR/core_expect.hex" ]]; then
  need_regen=1
elif [[ -f "$VECDIR/meta.txt" ]]; then
  current_seed="$(grep '^seed=' "$VECDIR/meta.txt" | cut -d= -f2 || true)"
  if [[ "$current_seed" != "$GOLDEN_SEED" ]]; then
    echo "cosim_core_narrow seed=$current_seed != required $GOLDEN_SEED — regenerating"
    need_regen=1
  fi
fi

if [[ "$need_regen" -eq 1 ]]; then
  echo "Generating narrow core vectors (keep=0.125, seed $GOLDEN_SEED, $GOLDEN_COUNT cases)..."
  (cd "$ROOT/python_ref" && python3 generate_vectors.py --narrow-core --keep 0.125 \
    --out-dir vectors/cosim_core_narrow --count "$GOLDEN_COUNT" --seed "$GOLDEN_SEED")
fi

echo "Exporting narrow C header..."
python3 "$ROOT/python_ref/tools/export_golden_narrow_c.py" "$VECDIR" "$OUTH"

echo "Ready: sw/golden_vectors_narrow.h (build bench with -DHDC_NARROW)"
