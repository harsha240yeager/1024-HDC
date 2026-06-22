#!/usr/bin/env bash
# Build Phase 2/3 bare-metal ELFs only (no Vivado XSA export).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
BSP="$ROOT/platform/ps7_cortexa9_0/standalone_domain/bsp"
SW="$REPO/sw"
BLD="$ROOT/app/build"
LSCRIPT="$ROOT/app/src/lscript.ld"

source /cad/Xilinx/Vitis/2024.2/settings64.sh

echo "== Golden vectors =="
( cd "$REPO" && bash scripts/prep_golden_test.sh )

echo "== Build standalone BSP (if needed) =="
make -C "$BSP"

mkdir -p "$BLD"

build_elf() {
  local name="$1"
  local main_c="$2"
  local suffix="$3"
  local out="$BLD/${name}.elf"
  local objs=()

  for f in "$main_c" hdc_dma_stream.c hdc_core_regs.c; do
    local obj="$BLD/${f%.c}.${suffix}.o"
    arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
      "-I$BSP/ps7_cortexa9_0/include" "-I$SW" \
      -c "$SW/$f" -o "$obj"
    objs+=("$obj")
  done

  arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
    -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
    "${objs[@]}" \
    "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
    -o "$out"
  arm-none-eabi-size "$out"
  echo "  -> $out"
}

echo "== Build Final_HDC_dma_golden.elf =="
build_elf Final_HDC_dma_golden hdc_dma_stream_golden_test.c golden

echo "== Build Final_HDC_dma_bench.elf =="
build_elf Final_HDC_dma_bench hdc_dma_stream_bench.c bench

echo "== Build Final_HDC_dma_batch_bench.elf =="
build_elf Final_HDC_dma_batch_bench hdc_dma_stream_batch_bench.c batch

echo "== EMG board vectors =="
if [[ ! -f "$SW/emg_board_vectors.h" ]]; then
  ( cd "$REPO" && bash scripts/prep_emg_board_test.sh )
fi

echo "== Build Final_HDC_dma_emg.elf =="
build_elf Final_HDC_dma_emg hdc_emg_board_test.c emg

echo "Done (SW only)."
