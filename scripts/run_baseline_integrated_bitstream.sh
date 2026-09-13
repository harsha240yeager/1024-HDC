#!/usr/bin/env bash
# Restore baseline (D=1024 + runtime mask) PL in Final_HDC and rebuild bitstream.
#
# Usage:
#   bash scripts/run_baseline_integrated_bitstream.sh
#   bash scripts/run_baseline_integrated_bitstream.sh --skip-vivado   # stage RTL only
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJ="${HDC_VIVADO_ROOT:-$HOME/Desktop/Final HDC/FInal_HDC}"
if [[ ! -f "$PROJ/FInal_HDC.xpr" && -f "$HOME/Final_HDC/FInal_HDC/FInal_HDC.xpr" ]]; then
  PROJ="$HOME/Final_HDC/FInal_HDC"
fi
RTL_DST="$PROJ/FInal_HDC.srcs/sources_1/rtl"
SKIP_VIVADO=0
[[ "${1:-}" == "--skip-vivado" ]] && SKIP_VIVADO=1

if [[ ! -f "$PROJ/FInal_HDC.xpr" ]]; then
  echo "ERROR: Vivado project not found at $PROJ" >&2
  exit 1
fi

if ! command -v vivado >/dev/null 2>&1; then
  if [[ -f /cad/Xilinx/Vivado/2024.2/settings64.sh ]]; then
    # shellcheck disable=SC1091
    source /cad/Xilinx/Vivado/2024.2/settings64.sh
  fi
fi

echo "== Sync baseline RTL -> $RTL_DST =="
mkdir -p "$RTL_DST"
rsync -a --delete \
  --exclude 'hdc_stream_system_bd_wrapper.sv' \
  --exclude 'hdc_stream_system_bd_wrapper_narrow.sv' \
  "$ROOT/rtl/" "$RTL_DST/"
cp -f "$ROOT/rtl/hdc_stream_system_bd_wrapper.sv" "$RTL_DST/hdc_stream_system_bd_wrapper.v"
cp -f "$ROOT/rtl/hdc_stream_system_bd_wrapper.sv" "$RTL_DST/hdc_stream_system_bd_wrapper.sv"

if [[ "$SKIP_VIVADO" -eq 1 ]]; then
  echo "RTL staged; Vivado skipped."
  exit 0
fi

mkdir -p "$ROOT/results/baseline_rtl"
LOG="$ROOT/results/baseline_rtl/integrated_synth.log"
echo "== Launch baseline synth + impl (log: $LOG) =="
export HDC_VIVADO_ROOT="$PROJ"
vivado -mode batch -notrace -source "$ROOT/scripts/rebuild_baseline_integrated.tcl" \
  -log "$LOG" -journal "$ROOT/results/baseline_rtl/integrated_synth.jou"

BIT="$PROJ/FInal_HDC.runs/impl_1/design_1_wrapper.bit"
DEST="$ROOT/board/HDC_DMA/app/_ide/bitstream/design_1_wrapper.bit"
mkdir -p "$(dirname "$DEST")"
cp -f "$BIT" "$DEST"
cp -f "$BIT" "$ROOT/board/HDC_DMA/platform/hw/design_1_wrapper.bit"
md5sum "$BIT" "$DEST"
echo "Done. Baseline bitstream staged for board/HDC_DMA."
