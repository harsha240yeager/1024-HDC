#!/usr/bin/env bash
# Build Phase 3 stream bench ELF.
# Preferred: board/HDC_DMA/build_sw.sh (integrated workspace BSP).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HDC_DMA="$REPO/board/HDC_DMA"

if [[ -x "$HDC_DMA/build_sw.sh" ]] && [[ "${HDC_BUILD_BENCH_LEGACY:-0}" != "1" ]]; then
  echo "=== Building via board/HDC_DMA/build_sw.sh ==="
  exec bash "$HDC_DMA/build_sw.sh"
fi

HDC_ROOT="${HDC_ROOT:-/home/bsp-lab/Desktop/Final HDC/HDC_harsha}"
BUILD="${HDC_BUILD:-$HDC_ROOT/hdc_dma_stream_bench/build}"
BSP="${HDC_BSP:-$HDC_ROOT/FInal_1024-HDC/export/FInal_1024-HDC/sw/standalone_ps7_cortexa9_0}"
LSCRIPT="${HDC_LSCRIPT:-$HDC_ROOT/hdc_dma_stream_bench/src/lscript.ld}"
SW="$REPO/sw"

if [[ ! -f /cad/Xilinx/Vitis/2024.2/settings64.sh ]]; then
  echo "ERROR: Vitis 2024.2 not found at /cad/Xilinx/Vitis/2024.2" >&2
  exit 1
fi

# shellcheck source=/dev/null
source /cad/Xilinx/Vitis/2024.2/settings64.sh
GCC=/cad/Xilinx/Vitis/2024.2/gnu/aarch32/lin/gcc-arm-none-eabi/bin/arm-none-eabi-gcc

mkdir -p "$BUILD/bench_obj"
CFLAGS=(-O0 -DSDT -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -MMD -MP
  -specs="$BSP/Xilinx.spec" -I"$BSP/include" -I"$SW" -Wall -Wextra -g3 -U__clang__)

for f in "$BSP/Xilinx.spec" "$LSCRIPT" "$SW/golden_vectors.h"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f" >&2
    echo "Run: bash scripts/prep_golden_test.sh" >&2
    echo "Set HDC_BSP / HDC_LSCRIPT if your Vitis workspace paths differ." >&2
    exit 1
  fi
done

"$GCC" "${CFLAGS[@]}" -c "$SW/hdc_dma_stream_bench.c" -o "$BUILD/bench_obj/hdc_dma_stream_bench.o"
"$GCC" "${CFLAGS[@]}" -c "$SW/hdc_dma_stream.c" -o "$BUILD/bench_obj/hdc_dma_stream.o"
"$GCC" "${CFLAGS[@]}" -c "$SW/hdc_core_regs.c" -o "$BUILD/bench_obj/hdc_core_regs.o"
"$GCC" "${CFLAGS[@]}" -o "$BUILD/hdc_dma_stream_bench.elf" \
  "$BUILD/bench_obj/hdc_dma_stream_bench.o" \
  "$BUILD/bench_obj/hdc_dma_stream.o" \
  "$BUILD/bench_obj/hdc_core_regs.o" \
  -Wl,-T -Wl,"$LSCRIPT" \
  -L"$BSP/lib" \
  -Wl,--start-group -lxilstandalone -lxiltimer -lxil -lxaxidma -lgcc -lc -lm -Wl,--end-group

arm-none-eabi-size "$BUILD/hdc_dma_stream_bench.elf"
echo "Built: $BUILD/hdc_dma_stream_bench.elf"
