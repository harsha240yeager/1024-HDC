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
PROJ="${HDC_VIVADO_ROOT:-$HOME/Final_HDC/FInal_HDC}"
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

# BD IP module name must stay hdc_stream_system_bd_wrapper; use narrow implementation.
cp "$ROOT/rtl/hdc_stream_system_bd_wrapper_narrow.sv" \
   "$RTL_DST/hdc_stream_system_bd_wrapper.sv"

if [[ -f "$RTL_DST/hdc_stream_system_bd_wrapper.v" ]]; then
  echo "NOTE: removing legacy .v wrapper so Vivado picks SystemVerilog narrow top"
  rm -f "$RTL_DST/hdc_stream_system_bd_wrapper.v"
fi

LOG="$ROOT/results/narrow_rtl/integrated_synth.log"
mkdir -p "$ROOT/results/narrow_rtl"
echo "== Launch integrated synth + impl (log: $LOG) =="
vivado -mode batch -notrace -source "$PROJ/rebuild_from_synth.tcl" \
  -log "$LOG" -journal "$ROOT/results/narrow_rtl/integrated_synth.jou"

echo "== Export util summary =="
UTIL="$PROJ/FInal_HDC.runs/impl_1/design_1_wrapper_utilization_placed.rpt"
if [[ -f "$UTIL" ]]; then
  cp "$UTIL" "$ROOT/results/narrow_rtl/integrated_utilization_placed.rpt"
  awk '/Slice LUTs/ || /Slice Registers/ {print}' "$UTIL" | head -4
fi

echo "Done. Bitstream + XSA under $PROJ/export/hw/"
