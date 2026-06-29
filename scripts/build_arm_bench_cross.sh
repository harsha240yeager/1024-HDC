#!/usr/bin/env bash
# Cross-compile Final_HDC_arm_bench.elf for ZedBoard (Cortex-A9).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="$ROOT/board/HDC_DMA"
BSP="$BOARD/platform/ps7_cortexa9_0/standalone_domain/bsp"
SW="$ROOT/sw"
BLD="$BOARD/app/build"
LSCRIPT="$BOARD/app/src/lscript.ld"

bash "$ROOT/scripts/prep_arm_bench.sh"

export PYTHONPATH="${PYTHONPATH:-}"
# shellcheck source=/dev/null
source /cad/Xilinx/Vitis/2024.2/settings64.sh

make -C "$BSP"
mkdir -p "$BLD"

OPT="-O2"
CFLAGS="-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard $OPT -g -Wall -I$BSP/ps7_cortexa9_0/include -I$SW"

arm-none-eabi-gcc $CFLAGS -c "$SW/hdc_arm_ref.c" -o "$BLD/hdc_arm_ref.arm.o"
arm-none-eabi-gcc $CFLAGS -c "$SW/hdc_arm_bench.c" -o "$BLD/hdc_arm_bench.arm.o"
arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard $OPT -g \
  -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
  "$BLD/hdc_arm_ref.arm.o" "$BLD/hdc_arm_bench.arm.o" \
  -L"$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
  -o "$BLD/Final_HDC_arm_bench.elf"

arm-none-eabi-size "$BLD/Final_HDC_arm_bench.elf"
echo "-> $BLD/Final_HDC_arm_bench.elf"
