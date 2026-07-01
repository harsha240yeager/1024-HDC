#!/usr/bin/env bash
# Verify host-side INA219 + I2C before energy measurement.
#
# Usage:
#   bash scripts/energy_preflight.sh
#   INA219_BUS=10 bash scripts/energy_preflight.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUS="${INA219_BUS:-}"
ADDR="${INA219_ADDR:-0x40}"
SHUNT="${INA219_SHUNT_MOHM:-100}"

echo "=== Energy measurement preflight ==="
echo ""

if ! python3 -c "import smbus2" 2>/dev/null; then
  echo "FAIL: smbus2 not installed"
  echo "  Fix: pip install smbus2"
  exit 1
fi
echo "OK   smbus2 installed"

if ! ls /dev/i2c-* &>/dev/null; then
  echo "FAIL: no /dev/i2c-* devices"
  echo "  Pi: sudo raspi-config → enable I2C, reboot"
  echo "  Ubuntu: plug in USB-I2C adapter (CP2112 or MCP2221A), then:"
  echo "        sudo modprobe i2c-dev"
  echo "        sudo usermod -aG i2c \$USER   # re-login after"
  exit 1
fi
echo "OK   I2C devices:"
ls -1 /dev/i2c-* | sed 's/^/       /'

if command -v i2cdetect &>/dev/null; then
  echo ""
  echo "Scanning buses (i2cdetect -l):"
  i2cdetect -l 2>/dev/null | sed 's/^/  /' || true
fi

echo ""
echo "Probing INA219 @ 0x$(printf '%02x' "$ADDR") ..."

probe_out="$(python3 - "$BUS" "$ADDR" "$SHUNT" <<'PY'
import sys
from smbus2 import SMBus

bus_arg = sys.argv[1]
addr = int(sys.argv[2], 0)
shunt_mohm = float(sys.argv[3])

def try_bus(n: int) -> tuple[bool, str]:
    try:
        b = SMBus(n)
    except OSError as e:
        return False, f"bus {n}: open failed ({e})"
    try:
        raw = b.read_i2c_block_data(addr, 0x02, 2)  # bus voltage reg
        bus_v = ((raw[0] << 8) | raw[1]) >> 3
        bus_v *= 0.004
        b.close()
        return True, f"bus {n}: INA219 responds, bus_v={bus_v:.3f} V"
    except OSError as e:
        b.close()
        return False, f"bus {n}: no response ({e})"

if bus_arg:
    ok, msg = try_bus(int(bus_arg))
    print(msg)
    sys.exit(0 if ok else 1)

found = []
for n in range(0, 32):
    path = f"/dev/i2c-{n}"
    try:
        open(path).close()
    except OSError:
        continue
    ok, msg = try_bus(n)
    print(msg)
    if ok:
        found.append(n)

if not found:
    sys.exit(1)
if len(found) == 1:
    print(f"\nSuggested: export INA219_BUS={found[0]}")
else:
    print(f"\nMultiple buses responded: {found}")
    print("Pick the USB adapter bus (often the highest number):")
    print(f"  export INA219_BUS={found[-1]}")
PY
)" || {
  echo "$probe_out"
  echo ""
  echo "FAIL: INA219 not found."
  echo "  Wiring: INA219 VCC→3.3V, GND→GND, SDA→SDA, SCL→SCL"
  echo "  Power path: 12V+ → INA219 Vin+ → Vin- → ZedBoard (+)"
  echo "  Retry: sudo i2cdetect -y <bus>   (expect 0x40)"
  exit 1
}

echo "$probe_out"
echo ""
echo "=== Preflight PASS ==="
echo ""
echo "Next (12 V input method):"
if [[ -r /proc/device-tree/model ]] && grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
  echo "  export INA219_BUS=${BUS:-1}"
  echo "  bash scripts/run_energy_log_pi.sh"
  echo "  (run bench on Ubuntu: bash board/HDC_DMA/run_phase3_bench_load.sh)"
else
  echo "  export INA219_BUS=${BUS:-<bus from above>}"
  echo "  export INA219_SHUNT_MOHM=100"
  echo "  export INA219_V_RAIL=12.0"
  echo "  bash scripts/run_energy_measure.sh"
fi
echo ""
echo "Or manual steps:"
echo "  python3 scripts/ina219_log.py --bus \$INA219_BUS --duration 5 --out /tmp/ina219_smoke.csv"
echo "  bash board/HDC_DMA/run_phase3_bench.sh"
