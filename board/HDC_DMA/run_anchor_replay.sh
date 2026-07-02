#!/usr/bin/env bash
# Hook A on-board anchor replay (A/B/C) — patch pruning mask, rebuild EMG ELF, run JTAG replay.
#
# Usage (from repo root or board/HDC_DMA):
#   bash board/HDC_DMA/run_anchor_replay.sh A
#   bash board/HDC_DMA/run_anchor_replay.sh B
#   bash board/HDC_DMA/run_anchor_replay.sh C
#   bash board/HDC_DMA/run_anchor_replay.sh ALL
#
# Prerequisite: sw/emg_board_vectors.bin + sw/emg_board_vectors.h (DDR pack from .full export).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
ANCHOR="${1:-}"

if [[ -z "$ANCHOR" ]]; then
  echo "Usage: $0 A|B|C|ALL" >&2
  exit 1
fi

anchor_keep() {
  case "$1" in
    A) echo "1.0" ;;
    B) echo "0.5" ;;
    C) echo "0.125" ;;
    *) return 1 ;;
  esac
}

run_one_anchor() {
  local id="$1"
  local keep
  local out_dir="$REPO/results/phase3/anchors/anchor_${id}"
  local log_dir="${HDC_LOG_DIR:-/tmp/hdc_anchor_${id}}"

  keep="$(anchor_keep "$id")" || {
    echo "Unknown anchor: $id" >&2
    return 1
  }

  mkdir -p "$out_dir" "$log_dir"

  echo "=== Anchor ${id}: keep_ratio=${keep} ==="

  if [[ "$id" == "A" && "${HDC_ANCHOR_SKIP_PATCH:-0}" == "1" ]]; then
    echo "Skipping mask patch for anchor A (HDC_ANCHOR_SKIP_PATCH=1)"
  else
    echo "Patching mask + export ref ..."
    python3 "$REPO/scripts/patch_emg_anchor.py" --anchor "$id" --keep-ratio "$keep"
  fi

  echo "Rebuilding Final_HDC_dma_emg.elf ..."
  (
    cd "$ROOT"
    export PYTHONPATH="${PYTHONPATH:-}"
    export PYTHONPATH="${PYTHONPATH:-}"
    source /cad/Xilinx/Vitis/2024.2/settings64.sh
    BSP="$ROOT/platform/ps7_cortexa9_0/standalone_domain/bsp"
    SW="$REPO/sw"
    BLD="$ROOT/app/build"
    LSCRIPT="$ROOT/app/src/lscript.ld"
    make -C "$BSP" >/dev/null
    mkdir -p "$BLD"
    objs=()
    for f in hdc_emg_board_test.c hdc_dma_stream.c hdc_core_regs.c; do
      obj="$BLD/${f%.c}.emg.o"
      arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
        "-I$BSP/ps7_cortexa9_0/include" "-I$SW" \
        -c "$SW/$f" -o "$obj"
      objs+=("$obj")
    done
    arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
      -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" \
      "${objs[@]}" \
      "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
      -o "$BLD/Final_HDC_dma_emg.elf"
    arm-none-eabi-size "$BLD/Final_HDC_dma_emg.elf"
  )

  echo "Running board EMG replay ..."
  export HDC_EMG_RESULTS="$out_dir/board_emg_replay.txt"
  export HDC_LOG_DIR="$log_dir"
  bash "$ROOT/run_phase3_emg.sh" | tee "$log_dir/run_anchor_${id}.log"

  echo "Anchor ${id} complete -> $HDC_EMG_RESULTS"
  grep -E "EMG replay:|Export ref:|Board vs export:|Status:" "$HDC_EMG_RESULTS" || true
}

if [[ "$ANCHOR" == "ALL" ]]; then
  for id in A B C; do
    run_one_anchor "$id"
  done
  echo "All anchors A/B/C complete under results/phase3/anchors/"
else
  run_one_anchor "$ANCHOR"
fi
