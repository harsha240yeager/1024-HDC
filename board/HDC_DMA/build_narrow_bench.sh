#!/usr/bin/env bash
# Build Final_HDC_dma_bench_narrow.elf (DMA bench with -DHDC_NARROW).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
BSP="$ROOT/platform/ps7_cortexa9_0/standalone_domain/bsp"
SW="$REPO/sw"
BLD="$ROOT/app/build"
LSCRIPT="$ROOT/app/src/lscript.ld"
OUT="$BLD/Final_HDC_dma_bench_narrow.elf"

source /cad/Xilinx/Vitis/2024.2/settings64.sh

bash "$REPO/scripts/prep_narrow_golden_test.sh"

make -C "$BSP" >/dev/null
mkdir -p "$BLD"

objs=()
for f in hdc_dma_stream_bench.c hdc_dma_stream.c hdc_core_regs.c; do
  obj="$BLD/${f%.c}.bench_narrow.o"
  arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
    -DHDC_NARROW \
    "-I$BSP/ps7_cortexa9_0/include" "-I$SW" \
    -c "$SW/$f" -o "$obj"
  objs+=("$obj")
done

arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
  -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
  "${objs[@]}" \
  "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
  -o "$OUT"
arm-none-eabi-size "$OUT"
echo "  -> $OUT"
