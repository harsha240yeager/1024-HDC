#!/usr/bin/env bash
# Manual build for hdc_core_bench.elf (Vitis cmake may fail on some hosts).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HDC_ROOT="${HDC_ROOT:-/home/bsp-lab/Desktop/Final HDC/HDC_harsha}"
BUILD="$HDC_ROOT/hdc_core_bench/build"
BSP="$HDC_ROOT/FInal_1024-HDC/export/FInal_1024-HDC/sw/standalone_ps7_cortexa9_0"
LSCRIPT="$HDC_ROOT/hdc_core_bench/src/lscript.ld"
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

"$GCC" "${CFLAGS[@]}" -c "$SW/hdc_core_bench.c" -o "$BUILD/bench_obj/hdc_core_bench.o"
"$GCC" "${CFLAGS[@]}" -c "$SW/hdc_core_regs.c" -o "$BUILD/bench_obj/hdc_core_regs.o"
"$GCC" "${CFLAGS[@]}" -o "$BUILD/hdc_core_bench.elf" \
  "$BUILD/bench_obj/hdc_core_bench.o" \
  "$BUILD/bench_obj/hdc_core_regs.o" \
  -Wl,-T -Wl,"$LSCRIPT" \
  -L"$BSP/lib" \
  -Wl,--start-group -lxilstandalone -lxiltimer -lxil -lgcc -lc -lm -Wl,--end-group

arm-none-eabi-size "$BUILD/hdc_core_bench.elf"
echo "Built: $BUILD/hdc_core_bench.elf"
