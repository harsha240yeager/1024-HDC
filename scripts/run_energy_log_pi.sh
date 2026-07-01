#!/usr/bin/env bash
# INA219 logging on Raspberry Pi (bench runs separately on Ubuntu/JTAG host).
#
# Two-machine workflow:
#   Pi  — this script (I2C / INA219 / power CSVs)
#   PC  — ZedBoard JTAG: run_phase3_program_pl.sh + run_phase3_bench_load.sh
#
# On the Pi (once):
#   sudo raspi-config  → Interface Options → I2C → Enable
#   sudo apt install -y python3-pip i2c-tools
#   pip3 install smbus2
#   sudo usermod -aG i2c $USER   # re-login
#
# Usage:
#   export INA219_BUS=1          # default on Pi
#   export INA219_SHUNT_MOHM=100
#   export INA219_V_RAIL=12.0
#   bash scripts/run_energy_log_pi.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${ENERGY_LOG_DIR:-$ROOT/results/phase3/logs}"
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
COUNTDOWN="${ENERGY_BENCH_COUNTDOWN:-5}"

mkdir -p "$LOG_DIR"

echo "=== Raspberry Pi energy logger ==="
echo "  I2C bus=$BUS  shunt=${SHUNT}mOhm  v_rail=${V_RAIL}V"
echo "  logs → $LOG_DIR"
echo ""

if ! python3 -c "import smbus2" 2>/dev/null; then
  echo "ERROR: pip3 install smbus2" >&2
  exit 1
fi

INA219_BUS="$BUS" bash "$ROOT/scripts/energy_preflight.sh" || exit 1
echo ""

echo "=== Step 1/3: Static power (ZedBoard idle, PL programmed) ==="
echo "On Ubuntu FIRST (if not done): bash board/HDC_DMA/run_phase3_program_pl.sh"
echo "Then ensure no bench is running. Logging ${STATIC_S}s..."
python3 "$ROOT/scripts/ina219_log.py" \
  --bus "$BUS" --address "$ADDR" --shunt-mohm "$SHUNT" \
  --duration "$STATIC_S" --out "$STATIC_CSV"
echo "Static CSV: $STATIC_CSV"
echo ""

echo "=== Step 2/3: Dynamic capture ==="
echo "This Pi will log ${BATCH_LOG_S}s starting in ${COUNTDOWN}s."
echo ""
echo "On Ubuntu (bsp-lab), be ready to run IMMEDIATELY after the countdown:"
echo "  cd ~/1024-HDC"
echo "  bash board/HDC_DMA/run_phase3_bench_load.sh"
echo ""
for ((i=COUNTDOWN; i>=1; i--)); do
  echo "  starting logger in ${i}..."
  sleep 1
done

python3 "$ROOT/scripts/ina219_log.py" \
  --bus "$BUS" --address "$ADDR" --shunt-mohm "$SHUNT" \
  --duration "$BATCH_LOG_S" --out "$BATCH_CSV" &
LOG_PID=$!

sleep 1
echo ""
echo ">>> RUN BENCH ON UBUNTU NOW <<<"
wait "$LOG_PID" || true
echo "Dynamic CSV: $BATCH_CSV"
echo ""

echo "=== Step 3/3: Integrate ==="
BATCH_MS=""
if [[ -f "$ROOT/results/phase3/board_bench.txt" ]]; then
  line="$(grep -E '^total[[:space:]]+=' "$ROOT/results/phase3/board_bench.txt" 2>/dev/null || true)"
  if [[ "$line" == *us* ]]; then
    us="$(echo "$line" | awk '{print $3}')"
    BATCH_MS="$(python3 -c "print(float('$us')/1000.0)")"
  fi
fi

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
echo "Done."
echo "  Summary: $SUMMARY"
echo "  Copy CSVs to repo on Ubuntu if needed:"
echo "    scp $STATIC_CSV $BATCH_CSV user@bsp-lab:~/1024-HDC/results/phase3/logs/"
