#!/usr/bin/env bash

# Phase 3 energy measurement helper (host-side INA219 + board batch bench).

#

# Flow (avoids bitstream-program spike during dynamic log):

#   1. Program PL only → idle static baseline

#   2. Log static power (INA219)

#   3. Log dynamic power while running bench ELF reload only (no PL reprogram)

#   4. Integrate → results/phase3/energy_batch.txt

#

# Prerequisites:

#   - INA219 + USB-I2C on Ubuntu (CP2112 or MCP2221A)

#   - pip install smbus2

#   - bash scripts/energy_preflight.sh  (once, to find INA219_BUS)

#   - board/HDC_DMA/build_sw.sh done

#

# Usage:

#   export INA219_BUS=10

#   export INA219_SHUNT_MOHM=100

#   export INA219_V_RAIL=12.0

#   bash scripts/run_energy_measure.sh

#

set -euo pipefail



ROOT="$(cd "$(dirname "$0")/.." && pwd)"

LOG_DIR="$ROOT/results/phase3/logs"

STATIC_CSV="$LOG_DIR/ina219_static.csv"

BATCH_CSV="$LOG_DIR/ina219_batch.csv"

SUMMARY="$ROOT/results/phase3/energy_batch.txt"



BUS="${INA219_BUS:-1}"

ADDR="${INA219_ADDR:-0x40}"

SHUNT="${INA219_SHUNT_MOHM:-100}"

V_RAIL="${INA219_V_RAIL:-12.0}"

STATIC_S="${INA219_STATIC_S:-10}"

BATCH_LOG_S="${INA219_BATCH_LOG_S:-30}"

BATCH_WINDOWS="${INA219_BATCH_WINDOWS:-200}"

SKIP_PROGRAM="${ENERGY_SKIP_PROGRAM:-0}"



mkdir -p "$LOG_DIR"



echo "Energy config: bus=$BUS addr=$ADDR shunt=${SHUNT}mOhm v_rail=${V_RAIL}V"

echo ""



if ! python3 -c "import smbus2" 2>/dev/null; then

  echo "ERROR: pip install smbus2" >&2

  exit 1

fi



if [[ "${ENERGY_RUN_PREFLIGHT:-1}" == "1" ]]; then

  echo "=== Preflight: INA219 on I2C ==="

  INA219_BUS="$BUS" bash "$ROOT/scripts/energy_preflight.sh" || exit 1

  echo ""

fi



if [[ "$SKIP_PROGRAM" != "1" ]]; then

  echo "=== Step 0: Program PL (idle, no inference) ==="

  bash "$ROOT/board/HDC_DMA/run_phase3_program_pl.sh"

  echo ""

fi



echo "=== Step 1/3: Static power (PL programmed, CPU idle) ==="

echo "Logging ${STATIC_S}s..."

python3 "$ROOT/scripts/ina219_log.py" \

  --bus "$BUS" --address "$ADDR" --shunt-mohm "$SHUNT" \

  --duration "$STATIC_S" --out "$STATIC_CSV"



echo ""

echo "=== Step 2/3: Dynamic batch (log + bench load-only) ==="

python3 "$ROOT/scripts/ina219_log.py" \

  --bus "$BUS" --address "$ADDR" --shunt-mohm "$SHUNT" \

  --duration "$BATCH_LOG_S" --out "$BATCH_CSV" &

LOG_PID=$!



sleep 2

echo "Starting Phase 3 bench (ELF reload only, no PL reprogram)..."

bash "$ROOT/board/HDC_DMA/run_phase3_bench_load.sh"



wait "$LOG_PID" || true



BATCH_MS=""

if [[ -f "$ROOT/results/phase3/board_bench.txt" ]]; then

  line="$(grep -E '^total[[:space:]]+=' "$ROOT/results/phase3/board_bench.txt" || true)"

  if [[ "$line" == *us* ]]; then

    us="$(echo "$line" | awk '{print $3}')"

    BATCH_MS="$(python3 -c "print(float('$us')/1000.0)")"

  elif [[ -n "$line" ]]; then

    BATCH_MS="$(echo "$line" | awk '{print $3}')"

  fi

fi



echo ""

echo "=== Step 3/3: Integrate and write summary ==="

INTEGRATE_ARGS=(

  --integrate "$BATCH_CSV"

  --static-csv "$STATIC_CSV"

  --shunt-mohm "$SHUNT"

  --v-rail "$V_RAIL"

  --batch-windows "$BATCH_WINDOWS"

  --summary-out "$SUMMARY"

)

if [[ -n "$BATCH_MS" ]]; then

  INTEGRATE_ARGS+=(--batch-duration-ms "$BATCH_MS")

fi



python3 "$ROOT/scripts/ina219_log.py" "${INTEGRATE_ARGS[@]}"



echo ""

echo "Done. Summary: $SUMMARY"

echo "Raw CSVs: $STATIC_CSV , $BATCH_CSV"

echo "Repeat 3x for mean ± std; set ENERGY_SKIP_PROGRAM=1 if PL already programmed."

