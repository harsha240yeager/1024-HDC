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

# ModelSim/Questa fallback.  Worth having: vlog and vopt check out **no license**,
# so this compile+elaborate check runs even where `vsim` cannot (e.g. off the
# network hosting the license server).
if ! command -v vlog >/dev/null 2>&1; then
  for d in "${MODELSIM_HOME:-}" /c/modeltech64_10.6e /c/questa_sim64_10.2 \
           "C:/modeltech64_10.6e" "C:/questa_sim64_10.2"; do
    if [[ -n "$d" && -x "$d/win64/vlog.exe" ]]; then
      export PATH="$d/win64:${PATH}"
      break
    fi
  done
fi

PY="python3"
command -v python3 >/dev/null 2>&1 && python3 -c "" 2>/dev/null || PY="python"

SRCS=(
  rtl/hdc_sel_pkg.sv
  rtl/item_mem.sv
  rtl/bundle_unit.sv
  rtl/encoder_top.sv
  rtl/popcount_am_narrow.sv
  rtl/hdc_core_top_narrow.sv
  tb/tb_core_narrow_cosim.sv
)

if command -v xvlog >/dev/null 2>&1; then
  echo "=== gen_sel_table --check ==="
  "$PY" scripts/gen_sel_table.py --check
  echo "=== xvlog narrow RTL + TB ==="
  xvlog -sv "${SRCS[@]}"
  echo "PASS: narrow RTL compiles cleanly (xvlog)"
elif command -v vlog >/dev/null 2>&1; then
  echo "=== gen_sel_table --check ==="
  "$PY" scripts/gen_sel_table.py --check
  WORK="$(mktemp -d)/work"
  echo "=== vlog narrow RTL + TB ==="
  vlib "$WORK"
  vlog -sv -work "$WORK" "${SRCS[@]}"
  echo "=== vopt elaborate tb_core_narrow_cosim ==="
  vopt -work "$WORK" tb_core_narrow_cosim -o tb_opt_check
  rm -rf "$(dirname "$WORK")"
  echo "PASS: narrow RTL compiles and elaborates cleanly (vlog + vopt)"
else
  echo "SKIP: no HDL compiler found."
  echo "  Tried xvlog (set XILINX_VIVADO or source Vivado settings64.sh)"
  echo "  and vlog  (set MODELSIM_HOME to a ModelSim/Questa install root)."
  echo "  Python-side checks still runnable:"
  echo "    $PY scripts/gen_sel_table.py --check"
  echo "    $PY scripts/verify_narrow_gather_equivalence.py --max-windows 5000"
  echo "    $PY scripts/verify_narrow_core_cosim_golden.py --count 500 --seed 42"
  exit 2
fi
