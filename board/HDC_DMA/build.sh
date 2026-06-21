#!/usr/bin/env bash
# Build HDC_DMA Vitis platform BSP + Phase 2 DMA golden/bench ELFs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
VIVADO_PROJ="${HDC_VIVADO_ROOT:-}"
BSP="$ROOT/platform/ps7_cortexa9_0/standalone_domain/bsp"
SW="$REPO/sw"
BLD="$ROOT/app/build"
LSCRIPT="$ROOT/app/src/lscript.ld"

if [[ -z "$VIVADO_PROJ" || ! -d "$VIVADO_PROJ" ]]; then
  echo "ERROR: set HDC_VIVADO_ROOT to your Vivado FInal_HDC project directory." >&2
  echo "  export HDC_VIVADO_ROOT=\"/path/to/FInal_HDC\"" >&2
  exit 1
fi

source /cad/Xilinx/Vitis/2024.2/settings64.sh
export PATH="/cad/Xilinx/Vivado/2024.2/bin:$PATH"

echo "== Export XSA (with bitstream) =="
vivado -mode batch -notrace -source "$VIVADO_PROJ/export_hw_platform.tcl" -log "$VIVADO_PROJ/export_hw_platform.log"

echo "== Stage platform hw =="
mkdir -p "$ROOT/platform/export/Final_HDC/hw"
cp -f "$VIVADO_PROJ/export/hw/design_1_wrapper.xsa" "$ROOT/platform/export/Final_HDC/hw/"
cp -f "$VIVADO_PROJ/FInal_HDC.runs/impl_1/design_1_wrapper.bit" \
      "$ROOT/app/_ide/bitstream/design_1_wrapper.bit"

echo "== Golden vectors =="
( cd "$REPO" && bash scripts/prep_golden_test.sh )

echo "== Build standalone BSP =="
make -C "$BSP"

echo "== Build FSBL =="
make -C "$ROOT/platform/zynq_fsbl"

echo "== Build Final_HDC_dma_golden.elf =="
mkdir -p "$BLD"
for f in hdc_dma_stream_golden_test.c hdc_dma_stream.c hdc_core_regs.c; do
  arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
    "-I$BSP/ps7_cortexa9_0/include" "-I$SW" \
    -c "$SW/$f" -o "$BLD/${f%.c}.o"
done
arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
  -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
  "$BLD/hdc_dma_stream_golden_test.o" "$BLD/hdc_dma_stream.o" "$BLD/hdc_core_regs.o" \
  "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
  -o "$BLD/Final_HDC_dma_golden.elf"
arm-none-eabi-size "$BLD/Final_HDC_dma_golden.elf"

echo "== Build Final_HDC_dma_bench.elf =="
for f in hdc_dma_stream_bench.c hdc_dma_stream.c hdc_core_regs.c; do
  arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
    "-I$BSP/ps7_cortexa9_0/include" "-I$SW" \
    -c "$SW/$f" -o "$BLD/${f%.c}.bench.o"
done
arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
  -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
  "$BLD/hdc_dma_stream_bench.bench.o" "$BLD/hdc_dma_stream.bench.o" "$BLD/hdc_core_regs.bench.o" \
  "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
  -o "$BLD/Final_HDC_dma_bench.elf"
arm-none-eabi-size "$BLD/Final_HDC_dma_bench.elf"

echo "== Build Final_HDC_dma_batch_bench.elf =="
for f in hdc_dma_stream_batch_bench.c hdc_dma_stream.c hdc_core_regs.c; do
  arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
    "-I$BSP/ps7_cortexa9_0/include" "-I$SW" \
    -c "$SW/$f" -o "$BLD/${f%.c}.batch.o"
done
arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
  -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
  "$BLD/hdc_dma_stream_batch_bench.batch.o" "$BLD/hdc_dma_stream.batch.o" "$BLD/hdc_core_regs.batch.o" \
  "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
  -o "$BLD/Final_HDC_dma_batch_bench.elf"
arm-none-eabi-size "$BLD/Final_HDC_dma_batch_bench.elf"

echo "Done."
echo "  Platform : $ROOT/platform/export/Final_HDC/Final_HDC.xpfm"
echo "  Bitstream: $ROOT/app/_ide/bitstream/design_1_wrapper.bit"
echo "  Golden ELF: $BLD/Final_HDC_dma_golden.elf"
echo "  Bench ELF  : $BLD/Final_HDC_dma_bench.elf"
echo "  Batch ELF  : $BLD/Final_HDC_dma_batch_bench.elf"
echo "  FSBL       : $ROOT/platform/zynq_fsbl/fsbl.elf"
