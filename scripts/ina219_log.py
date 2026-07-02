#!/usr/bin/env python3
"""
Log INA219 power during Phase 3 energy measurement.

Typical workflow (host or ZedBoard Linux with I2C):

  # Terminal 1 — idle static power (bitstream programmed, no inference)
  python3 scripts/ina219_log.py --duration 10 --out results/phase3/logs/ina219_static.csv

  # Terminal 2 — run batch bench while logging dynamic power
  python3 scripts/ina219_log.py --duration 30 --out results/phase3/logs/ina219_batch.csv &
  bash board/HDC_DMA/run_phase3_bench.sh

  # Summarize (uses static mean as baseline)
  python3 scripts/ina219_log.py --integrate results/phase3/logs/ina219_batch.csv \\
      --static-csv results/phase3/logs/ina219_static.csv \\
      --batch-windows 200 --summary-out results/phase3/energy_batch.txt

Requires: pip install smbus2
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# INA219 register map
_REG_CONFIG = 0x00
_REG_SHUNT = 0x01
_REG_BUS = 0x02
_REG_POWER = 0x03
_REG_CURRENT = 0x04
_REG_CALIB = 0x05

# Continuous shunt + bus, 128-sample avg, 1.1 ms conversion (good for ~100 Hz logging)
_CONFIG_DEFAULT = 0x019F


class INA219:
    """Minimal INA219 reader over smbus2."""

    def __init__(self, bus: int, address: int, shunt_mohm: float) -> None:
        try:
            from smbus2 import SMBus
        except ImportError as exc:
            raise SystemExit(
                "smbus2 not installed. Run: pip install smbus2"
            ) from exc

        if shunt_mohm <= 0:
            raise ValueError("shunt_mohm must be positive")

        self._bus = SMBus(bus)
        self._addr = address
        self._shunt_ohm = shunt_mohm / 1000.0
        self._cal = self._compute_calibration(shunt_mohm)

        self._bus.write_i2c_block_data(self._addr, _REG_CONFIG, [(_CONFIG_DEFAULT >> 8) & 0xFF, _CONFIG_DEFAULT & 0xFF])
        cal = self._cal & 0xFFFF
        self._bus.write_i2c_block_data(self._addr, _REG_CALIB, [(cal >> 8) & 0xFF, cal & 0xFF])

    def close(self) -> None:
        self._bus.close()

    @staticmethod
    def _compute_calibration(shunt_mohm: float) -> int:
        # Cal = 0.04096 / (Current_LSB * R_shunt); Current_LSB = 1 mA here
        current_lsb_a = 0.001
        r_shunt = shunt_mohm / 1000.0
        cal = int(0.04096 / (current_lsb_a * r_shunt))
        return max(1, min(cal, 0xFFFF))

    def _read_u16(self, reg: int) -> int:
        raw = self._bus.read_i2c_block_data(self._addr, reg, 2)
        val = (raw[0] << 8) | raw[1]
        if val & 0x8000:
            val -= 1 << 16
        return val

    def read(self) -> dict[str, float]:
        shunt_raw = self._read_u16(_REG_SHUNT)
        bus_raw = self._read_u16(_REG_BUS)
        current_raw = self._read_u16(_REG_CURRENT)
        power_raw = self._read_u16(_REG_POWER)

        shunt_v = shunt_raw * 1e-5
        bus_v = (bus_raw >> 3) * 0.004
        current_a = current_raw * 0.001
        power_w = power_raw * 0.002

        return {
            "bus_v": bus_v,
            "shunt_mv": shunt_v * 1000.0,
            "current_ma": current_a * 1000.0,
            "power_mw": power_w * 1000.0,
        }


def log_samples(
    ina: INA219,
    duration_s: float,
    rate_hz: float,
    out_path: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    period = 1.0 / rate_hz
    t_end = time.monotonic() + duration_s
    t0 = time.monotonic()

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["t_s", "bus_v", "shunt_mv", "current_ma", "power_mw"],
        )
        writer.writeheader()

        while time.monotonic() < t_end:
            loop_start = time.monotonic()
            sample = ina.read()
            sample["t_s"] = loop_start - t0
            writer.writerow(sample)
            elapsed = time.monotonic() - loop_start
            sleep_s = period - elapsed
            if sleep_s > 0:
                time.sleep(sleep_s)


def load_csv(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append({k: float(row[k]) for k in row})
    return rows


def mean_power_mw(rows: list[dict[str, float]]) -> float:
    if not rows:
        return 0.0
    return sum(r["power_mw"] for r in rows) / len(rows)


def integrate_energy_mj(rows: list[dict[str, float]], baseline_mw: float) -> float:
    """Trapezoidal integration of (P - baseline) over time → mJ."""
    if len(rows) < 2:
        return 0.0
    energy_j = 0.0
    for i in range(1, len(rows)):
        dt = rows[i]["t_s"] - rows[i - 1]["t_s"]
        p0 = max(0.0, rows[i - 1]["power_mw"] - baseline_mw)
        p1 = max(0.0, rows[i]["power_mw"] - baseline_mw)
        energy_j += (p0 + p1) * 0.5 * dt / 1000.0
    return energy_j * 1000.0


def write_summary(
    path: Path,
    *,
    shunt_mohm: float,
    v_rail: float,
    batch_windows: int,
    p_static_mw: float,
    e_dynamic_mj: float,
    batch_duration_ms: float,
    notes: str = "",
) -> None:
    e_per_window_uj = (e_dynamic_mj * 1000.0 / batch_windows) if batch_windows else 0.0
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"""Phase 3 — Energy measurement results
=====================================
Date: {time.strftime('%Y-%m-%dT%H:%M:%S')}
Status: MEASURED

Hardware
--------
Shunt (mOhm): {shunt_mohm}
V rail (V):   {v_rail}
Sensor:       INA219

Batch inference (DMA stream path)
---------------------------------
Batch windows:      {batch_windows}
Batch duration (ms): {batch_duration_ms:.3f}
Static power (mW):  {p_static_mw:.3f}
Dynamic energy (mJ): {e_dynamic_mj:.6f}
Energy per window (uJ): {e_per_window_uj:.3f}

Notes
-----
{notes.strip() or '(none)'}
"""
    path.write_text(text, encoding="utf-8")
    print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="INA219 logger for Phase 3 energy")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (/dev/i2c-N)")
    parser.add_argument("--address", type=lambda x: int(x, 0), default=0x40, help="INA219 I2C address")
    parser.add_argument("--shunt-mohm", type=float, default=10.0, help="Shunt (mOhm): 10=ZedBoard J21, 100=Adafruit inline")
    parser.add_argument("--v-rail", type=float, default=1.0, help="Monitored rail voltage (V), for records")
    parser.add_argument("--duration", type=float, default=30.0, help="Log duration (seconds)")
    parser.add_argument("--rate-hz", type=float, default=100.0, help="Sample rate")
    parser.add_argument("--out", type=Path, default=REPO / "results" / "phase3" / "logs" / "ina219.csv")
    parser.add_argument("--integrate", type=Path, help="Integrate an existing CSV instead of logging")
    parser.add_argument("--static-csv", type=Path, help="Static baseline CSV for integration")
    parser.add_argument("--static-mw", type=float, help="Static power override (mW)")
    parser.add_argument("--batch-windows", type=int, default=200)
    parser.add_argument("--batch-duration-ms", type=float, default=0.0, help="From board_bench.txt if known")
    parser.add_argument("--summary-out", type=Path, default=REPO / "results" / "phase3" / "energy_batch.txt")
    args = parser.parse_args()

    if args.integrate:
        rows = load_csv(args.integrate)
        if args.static_mw is not None:
            p_static = args.static_mw
        elif args.static_csv:
            p_static = mean_power_mw(load_csv(args.static_csv))
        else:
            p_static = mean_power_mw(rows[: max(1, int(0.1 * len(rows)))])
            print(f"Warning: no static baseline; using first 10% mean = {p_static:.3f} mW")

        e_dyn = integrate_energy_mj(rows, p_static)
        batch_ms = args.batch_duration_ms
        if batch_ms <= 0 and len(rows) >= 2:
            batch_ms = (rows[-1]["t_s"] - rows[0]["t_s"]) * 1000.0

        write_summary(
            args.summary_out,
            shunt_mohm=args.shunt_mohm,
            v_rail=args.v_rail,
            batch_windows=args.batch_windows,
            p_static_mw=p_static,
            e_dynamic_mj=e_dyn,
            batch_duration_ms=batch_ms,
            notes=f"Integrated from {args.integrate}",
        )
        return 0

    print("INA219 logger")
    print(f"  bus={args.bus} addr=0x{args.address:02x} shunt={args.shunt_mohm} mOhm")
    print(f"  duration={args.duration}s @ {args.rate_hz} Hz")
    print(f"  output={args.out}")
    print()

    ina = INA219(args.bus, args.address, args.shunt_mohm)
    try:
        log_samples(ina, args.duration, args.rate_hz, args.out)
    finally:
        ina.close()

    rows = load_csv(args.out)
    print(f"Logged {len(rows)} samples. Mean power = {mean_power_mw(rows):.3f} mW")
    print("Next: run batch bench during a second log, then --integrate with --static-csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
