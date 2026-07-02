#!/usr/bin/env bash
# One INA219 energy run: Pi static + dynamic log, Ubuntu bench trigger, integrate.
#
# Environment:
#   ENERGY_RUN_DIR     output dir (required)
#   ENERGY_BENCH_CMD   shell command on Ubuntu at countdown (required)
#   ENERGY_BATCH_MS    batch duration for integration (required)
#   ENERGY_BATCH_WINDOWS default 200
#   ENERGY_ANCHOR      label for notes (A/B/C/ARM)
#   PI_HOST            default iitbbs@10.10.38.31
#   PI_PASS            default lab@123
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="${ENERGY_RUN_DIR:?set ENERGY_RUN_DIR}"
BENCH_CMD="${ENERGY_BENCH_CMD:?set ENERGY_BENCH_CMD}"
BATCH_MS="${ENERGY_BATCH_MS:?set ENERGY_BATCH_MS}"
# If bench wrote batch_ms.txt, prefer measured value (PL energy mode).
BENCH_MS_FILE="${ENERGY_BENCH_MS_FILE:-}"
if [[ -z "$BENCH_MS_FILE" && "$BENCH_CMD" == *bench_load_energy* ]]; then
  BENCH_MS_FILE="/tmp/hdc_phase3_bench_load_energy/batch_ms.txt"
fi
if [[ -n "$BENCH_MS_FILE" && -f "$BENCH_MS_FILE" ]]; then
  BATCH_MS="$(cat "$BENCH_MS_FILE" | sed -n 's/BATCH_MS=//p')"
fi
if [[ "$BENCH_CMD" == *arm_bench_load_energy* ]]; then
  BENCH_MS_FILE="${BENCH_MS_FILE:-/tmp/hdc_arm_bench_load_energy/batch_ms.txt}"
  if [[ -f "$BENCH_MS_FILE" ]]; then
    BATCH_MS="$(cat "$BENCH_MS_FILE" | sed -n 's/BATCH_MS=//p')"
  fi
fi
BATCH_WINDOWS="${ENERGY_BATCH_WINDOWS:-200}"
ANCHOR="${ENERGY_ANCHOR:-?}"
PI_HOST="${PI_HOST:-iitbbs@10.10.38.31}"
PI_PASS="${PI_PASS:-lab@123}"

CAL_ENV="$ROOT/results/phase3/energy_cal.env"
STATIC_CSV="$RUN_DIR/ina219_static.csv"
BATCH_CSV="$RUN_DIR/ina219_batch.csv"
SUMMARY="$RUN_DIR/energy_batch.txt"
STATIC_S="${INA219_STATIC_S:-10}"
BATCH_LOG_S="${INA219_BATCH_LOG_S:-30}"
COUNTDOWN="${ENERGY_BENCH_COUNTDOWN:-5}"

mkdir -p "$RUN_DIR"
REL_RUN="${RUN_DIR#${ROOT}/}"
PI_REPO='~/1024-HDC'

if [[ -f "$CAL_ENV" ]]; then
  # shellcheck source=/dev/null
  source "$CAL_ENV"
fi
BUS="${INA219_BUS:-1}"
ADDR="${INA219_ADDR:-0x40}"
SHUNT="${INA219_SHUNT_MOHM:-10}"
V_RAIL="${INA219_V_RAIL:-12.0}"
CAL_REF_MV="${INA219_CAL_REF_MV:-2.0}"

CAL_ARGS=(--cal-ref-mv "$CAL_REF_MV")
INTEGRATE_NOTE="anchor=${ANCHOR} mask=pooled_fisher golden+emg batch=${BATCH_MS}ms windows=${BATCH_WINDOWS} cal_ref_mv=${CAL_REF_MV}"

ssh_pi() {
  sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no "$PI_HOST" "$@"
}

scp_from_pi() {
  sshpass -p "$PI_PASS" scp -o StrictHostKeyChecking=no "$PI_HOST:$1" "$2"
}

echo "=== Energy run anchor=${ANCHOR} -> $RUN_DIR ==="

echo "--- Pi: static ${STATIC_S}s ---"
ssh_pi "mkdir -p ${PI_REPO}/${REL_RUN} && cd ${PI_REPO} && INA219_BUS=$BUS python3 scripts/ina219_log.py \
  --bus $BUS --address $ADDR --shunt-mohm $SHUNT \
  --cal-ref-mv $CAL_REF_MV --duration $STATIC_S --out ${PI_REPO}/${REL_RUN}/ina219_static.csv"

echo "--- Pi: dynamic ${BATCH_LOG_S}s (countdown ${COUNTDOWN}s) ---"
ssh_pi "cd ${PI_REPO} && python3 scripts/ina219_log.py \
  --bus $BUS --address $ADDR --shunt-mohm $SHUNT \
  --cal-ref-mv $CAL_REF_MV --duration $BATCH_LOG_S --out ${PI_REPO}/${REL_RUN}/ina219_batch.csv" &
PI_PID=$!

sleep 1
for ((i=COUNTDOWN; i>=1; i--)); do
  echo "  bench in ${i}..."
  sleep 1
done

echo "--- Ubuntu: $BENCH_CMD ---"
set +e
eval "$BENCH_CMD"
BENCH_RC=$?
set -e
if [[ "$BENCH_RC" -ne 0 ]]; then
  echo "WARNING: bench command exit $BENCH_RC (continuing to fetch Pi CSVs)" >&2
fi

wait "$PI_PID" || true

scp_from_pi "${PI_REPO}/${REL_RUN}/ina219_static.csv" "$STATIC_CSV"
scp_from_pi "${PI_REPO}/${REL_RUN}/ina219_batch.csv" "$BATCH_CSV"

echo "--- Integrate ---"
python3 "$ROOT/scripts/ina219_log.py" \
  --integrate "$BATCH_CSV" \
  --static-csv "$STATIC_CSV" \
  --shunt-mohm "$SHUNT" \
  --v-rail "$V_RAIL" \
  --batch-windows "$BATCH_WINDOWS" \
  --batch-duration-ms "$BATCH_MS" \
  --integrate-mode batch \
  --summary-out "$SUMMARY" \
  --notes "$INTEGRATE_NOTE"

grep -E "Static power|Total energy per window|Dynamic energy per window" "$SUMMARY" || true
echo "Run complete: $SUMMARY"
