#!/usr/bin/env bash
# Build hdc_arm_ref for host verification (VDI) or document cross-compile for Zynq.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SW="$ROOT/sw"
OUT="$ROOT/build/host"
mkdir -p "$OUT"

MODE="${1:-shared}"

echo "== hdc_arm_ref host build ($MODE) =="

if [[ "$MODE" == "shared" ]]; then
  gcc -O2 -Wall -Wextra -fPIC -shared \
    "$SW/hdc_arm_ref.c" -o "$OUT/libhdc_arm_ref.so"
  echo "  -> $OUT/libhdc_arm_ref.so"
elif [[ "$MODE" == "test" ]]; then
  gcc -O2 -Wall -Wextra -DHDC_ARM_REF_MAIN \
    "$SW/hdc_arm_ref.c" -o "$OUT/hdc_arm_ref_test"
  "$OUT/hdc_arm_ref_test" "$ROOT/python_ref/mem_files"
  echo "  -> $OUT/hdc_arm_ref_test PASS"
else
  echo "Usage: $0 [shared|test]" >&2
  exit 1
fi
