#!/usr/bin/env bash
# #29 integrated synthesis: sync narrow RTL into Final_HDC and rebuild bitstream.
#
# Prereqs:
#   Vivado + Vitis 2024.2 on PATH (/cad/Xilinx/...)
#   Final_HDC Vivado project (default: ~/Final_HDC/FInal_HDC)
#
# Usage:
#   export HDC_VIVADO_ROOT=/path/to/FInal_HDC
#   bash scripts/run_narrow_integrated_bitstream.sh
#
# This swaps the PL module to the narrow bd wrapper (same top name for the BD IP),
# copies repo RTL into the Vivado project, and runs rebuild_from_synth.tcl.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Default to the path baked into FInal_HDC.xpr (project was created under Desktop).
PROJ="${HDC_VIVADO_ROOT:-$HOME/Desktop/Final HDC/FInal_HDC}"
if [[ ! -f "$PROJ/FInal_HDC.xpr" && -f "$HOME/Final_HDC/FInal_HDC/FInal_HDC.xpr" ]]; then
  PROJ="$HOME/Final_HDC/FInal_HDC"
fi
RTL_DST="$PROJ/FInal_HDC.srcs/sources_1/rtl"

if [[ ! -f "$PROJ/FInal_HDC.xpr" ]]; then
  echo "ERROR: Vivado project not found at $PROJ" >&2
  echo "  export HDC_VIVADO_ROOT=/path/to/FInal_HDC" >&2
  exit 1
fi

if ! command -v vivado >/dev/null 2>&1; then
  if [[ -f /cad/Xilinx/Vivado/2024.2/settings64.sh ]]; then
    # shellcheck disable=SC1091
    source /cad/Xilinx/Vivado/2024.2/settings64.sh
  fi
fi

echo "== Ensure anchor-C SEL package =="
python3 "$ROOT/scripts/gen_sel_table.py" --check

echo "== Sync repo RTL -> $RTL_DST =="
mkdir -p "$RTL_DST"
rsync -a --delete \
  --exclude 'hdc_stream_system_bd_wrapper.sv' \
  "$ROOT/rtl/" "$RTL_DST/"

# BD IP expects module hdc_stream_system_bd_wrapper (not *_narrow).
# BD IP module_ref requires a Verilog (.v) top — not SystemVerilog.
sed -e 's/module hdc_stream_system_bd_wrapper_narrow/module hdc_stream_system_bd_wrapper/' \
    -e 's/localparam int K_BITS = hdc_sel_pkg::K_BITS;/localparam K_BITS = 128;/' \
  "$ROOT/rtl/hdc_stream_system_bd_wrapper_narrow.sv" \
  > "$RTL_DST/hdc_stream_system_bd_wrapper.v"
# Keep .sv for OOC synth scripts; exclude from integrated BD top.
sed 's/module hdc_stream_system_bd_wrapper_narrow/module hdc_stream_system_bd_wrapper/' \
  "$ROOT/rtl/hdc_stream_system_bd_wrapper_narrow.sv" \
  > "$RTL_DST/hdc_stream_system_bd_wrapper.sv"

echo "== Vivado project: $PROJ =="

LOG="$ROOT/results/narrow_rtl/integrated_synth.log"
mkdir -p "$ROOT/results/narrow_rtl"
echo "== Launch integrated synth + impl (log: $LOG) =="
export HDC_VIVADO_ROOT="$PROJ"
vivado -mode batch -notrace -source "$ROOT/scripts/rebuild_narrow_integrated.tcl" \
  -log "$LOG" -journal "$ROOT/results/narrow_rtl/integrated_synth.jou"

echo "== Export util summary =="
UTIL="$PROJ/FInal_HDC.runs/impl_1/design_1_wrapper_utilization_placed.rpt"
if [[ -f "$UTIL" ]]; then
  cp "$UTIL" "$ROOT/results/narrow_rtl/integrated_utilization_placed.rpt"
  awk '/Slice LUTs/ || /Slice Registers/ {print}' "$UTIL" | head -4
fi

echo "Done. Bitstream + XSA under $PROJ/export/hw/"
