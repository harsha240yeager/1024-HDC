#!/usr/bin/env bash
# #29 step 4: syntax / elaboration check for narrow RTL (no simulation).
#
# Usage (from repo root):
#   bash scripts/run_narrow_compile_check.sh
#
# Requires Vivado/Questa xvlog in PATH, or set XILINX_VIVADO to the install root.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v xvlog >/dev/null 2>&1; then
  if [[ -n "${XILINX_VIVADO:-}" && -x "${XILINX_VIVADO}/bin/xvlog" ]]; then
    export PATH="${XILINX_VIVADO}/bin:${PATH}"
  fi
fi

if ! command -v xvlog >/dev/null 2>&1; then
  echo "SKIP: xvlog not in PATH (set XILINX_VIVADO or source Vivado settings64.sh)"
  echo "  Python-side checks still runnable:"
  echo "    python3 scripts/gen_sel_table.py --check"
  echo "    python3 scripts/verify_narrow_gather_equivalence.py --max-windows 5000"
  exit 2
fi

echo "=== gen_sel_table --check ==="
python3 scripts/gen_sel_table.py --check

echo "=== xvlog narrow RTL + TB ==="
xvlog -sv \
  rtl/hdc_sel_pkg.sv \
  rtl/item_mem.sv \
  rtl/bundle_unit.sv \
  rtl/encoder_top.sv \
  rtl/popcount_am_narrow.sv \
  rtl/hdc_core_top_narrow.sv \
  tb/tb_core_narrow_cosim.sv

echo "PASS: narrow RTL elaborates cleanly"
