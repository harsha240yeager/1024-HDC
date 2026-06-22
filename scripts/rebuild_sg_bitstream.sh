#!/usr/bin/env bash
# Regenerate bitstream with scatter-gather AXI DMA, rebuild Vitis BSP + bench ELFs.
#
# Prereq: Vivado 2024.2 at /cad/Xilinx/Vivado/2024.2, Vitis 2024.2.
#
# Usage:
#   export HDC_VIVADO_ROOT="/home/bsp-lab/Final_HDC/FInal_HDC"
#   bash scripts/rebuild_sg_bitstream.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VIVADO_PROJ="${HDC_VIVADO_ROOT:-/home/bsp-lab/Final_HDC/FInal_HDC}"

if [[ ! -f "$VIVADO_PROJ/FInal_HDC.xpr" ]]; then
  echo "ERROR: Vivado project not found at $VIVADO_PROJ" >&2
  echo "  export HDC_VIVADO_ROOT=/path/to/FInal_HDC" >&2
  exit 1
fi

export PATH="/cad/Xilinx/Vivado/2024.2/bin:/cad/Xilinx/Vitis/2024.2/bin:$PATH"
set +u
source /cad/Xilinx/Vitis/2024.2/settings64.sh
set -u

echo "== Step 1/3: Enable scatter-gather in block design =="
vivado -mode batch -notrace -source "$VIVADO_PROJ/enable_sg_dma.tcl" \
  -log "$VIVADO_PROJ/enable_sg_dma.log"

echo "== Step 2/3: Synthesize + implement + export XSA/bitstream =="
export HDC_FORCE_BITSTREAM_REBUILD=1
vivado -mode batch -notrace -source "$VIVADO_PROJ/export_hw_platform.tcl" \
  -log "$VIVADO_PROJ/export_hw_platform_sg.log"
unset HDC_FORCE_BITSTREAM_REBUILD

echo "== Step 3/3: Rebuild BSP + bench ELFs =="
export HDC_VIVADO_ROOT="$VIVADO_PROJ"
bash "$REPO/board/HDC_DMA/build.sh"

echo ""
echo "Done. Program the board and run:"
echo "  cd $REPO/board/HDC_DMA && bash run_phase3_bench.sh"
