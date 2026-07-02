#!/usr/bin/env bash
# Resume energy campaign from anchor A run02 (run01 already integrated).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="$ROOT/board/HDC_DMA"
LOG="$ROOT/results/phase3/energy_runs/campaign_resume.log"
PL_BENCH="bash $BOARD/run_phase3_bench_load_energy.sh"
ARM_BENCH="bash $BOARD/run_arm_bench_load_energy.sh"
PL_BATCH_MS="0.926"
ARM_BATCH_MS="163.6"

exec > >(tee -a "$LOG") 2>&1

run_three() {
  local anchor="$1" bench_cmd="$2" batch_ms="$3" windows="${4:-200}" start_run="${5:-01}"
  local base="$ROOT/results/phase3/energy_runs/anchor_${anchor}"
  mkdir -p "$base"
  local run
  for run in 01 02 03; do
    [[ "$run" < "$start_run" ]] && continue
    echo "=== ${anchor} run ${run}/3 ==="
    ENERGY_RUN_DIR="$base/run${run}" ENERGY_BENCH_CMD="$bench_cmd" \
      ENERGY_BATCH_MS="$batch_ms" ENERGY_BATCH_WINDOWS="$windows" ENERGY_ANCHOR="$anchor" \
      bash "$ROOT/scripts/run_energy_one_run.sh"
  done
}

patch_anchor() { python3 "$ROOT/scripts/patch_emg_anchor.py" --anchor "$1" --skip-accuracy; }
program_pl_idle() { bash "$BOARD/run_phase3_program_pl.sh"; }
aggregate_anchor() { python3 "$ROOT/scripts/aggregate_energy_runs.py" --anchor "$1"; }

rebuild_pl_bench() {
  export PYTHONPATH="${PYTHONPATH:-}"
  (
    cd "$BOARD"
    source /cad/Xilinx/Vitis/2024.2/settings64.sh
    BSP="$BOARD/platform/ps7_cortexa9_0/standalone_domain/bsp"
    SW="$ROOT/sw" BLD="$BOARD/app/build" LSCRIPT="$BOARD/app/src/lscript.ld"
    make -C "$BSP" >/dev/null && mkdir -p "$BLD"
    objs=()
    for f in hdc_dma_stream_bench.c hdc_dma_stream.c hdc_core_regs.c; do
      obj="$BLD/${f%.c}.bench.o"
      arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g -Wall \
        "-I$BSP/ps7_cortexa9_0/include" "-I$SW" -c "$SW/$f" -o "$obj"
      objs+=("$obj")
    done
    arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g \
      -specs="$BSP/Xilinx.spec" -T "$LSCRIPT" "${objs[@]}" \
      "-L$BSP/ps7_cortexa9_0/lib" -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group \
      -o "$BLD/Final_HDC_dma_bench.elf"
  )
}

rebuild_arm_bench() {
  bash "$ROOT/scripts/prep_arm_bench.sh"
  python3 "$ROOT/python_ref/tools/verify_arm_bench_golden.py"
  bash "$ROOT/scripts/build_arm_bench_cross.sh"
}

echo "=== Resume campaign $(date -Iseconds) ==="

# A run02-03 (mask already patched)
program_pl_idle
run_three A "$PL_BENCH" "$PL_BATCH_MS" 200 02
aggregate_anchor A

patch_anchor B
rebuild_pl_bench
program_pl_idle
run_three B "$PL_BENCH" "$PL_BATCH_MS" 200 01
aggregate_anchor B

patch_anchor C
rebuild_pl_bench
program_pl_idle
run_three C "$PL_BENCH" "$PL_BATCH_MS" 200 01
aggregate_anchor C

patch_anchor A
rebuild_arm_bench
program_pl_idle
run_three ARM "$ARM_BENCH" "$ARM_BATCH_MS" 200 01
aggregate_anchor ARM

python3 "$ROOT/scripts/aggregate_energy_runs.py" --write-summary
echo "=== Resume campaign complete $(date -Iseconds) ==="
