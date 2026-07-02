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
import os
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


def apply_cal_gain(sample: dict[str, float], gain: float) -> dict[str, float]:
    """Scale shunt/current for J21 sense-wire attenuation; recompute P = V × I."""
    if gain == 1.0:
        return sample
    out = dict(sample)
    out["shunt_mv"] *= gain
    out["current_ma"] *= gain
    out["power_mw"] = abs(out["bus_v"] * out["current_ma"])
    return out


def resolve_cal_gain(
    cal_gain: float | None,
    cal_ref_mv: float | None,
    ina: INA219,
    *,
    settle_s: float,
    rate_hz: float,
) -> float:
    """Return multiplier: explicit gain, or ref_mV / mean raw |shunt_mv|."""
    if cal_gain is not None and cal_gain > 0:
        return cal_gain
    if cal_ref_mv is None or cal_ref_mv <= 0:
        return 1.0

    period = 1.0 / rate_hz
    t_end = time.monotonic() + settle_s
    shunt_vals: list[float] = []
    while time.monotonic() < t_end:
        loop_start = time.monotonic()
        shunt_vals.append(abs(ina.read()["shunt_mv"]))
        elapsed = time.monotonic() - loop_start
        sleep_s = period - elapsed
        if sleep_s > 0:
            time.sleep(sleep_s)

    mean_shunt = sum(shunt_vals) / len(shunt_vals) if shunt_vals else 0.0
    if mean_shunt < 1e-6:
        raise SystemExit(
            "ERROR: --cal-ref-mv needs non-zero raw shunt_mv; check J21 Vin+/Vin− wiring."
        )
    gain = cal_ref_mv / mean_shunt
    print(
        f"Calibration: ref={cal_ref_mv:.3f} mV  raw_mean={mean_shunt:.4f} mV  "
        f"gain={gain:.3f}x"
    )
    return gain


def log_samples(
    ina: INA219,
    duration_s: float,
    rate_hz: float,
    out_path: Path,
    *,
    cal_gain: float = 1.0,
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
            sample = apply_cal_gain(ina.read(), cal_gain)
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


def slice_rows_by_time(
    rows: list[dict[str, float]],
    t_start: float,
    t_end: float,
) -> list[dict[str, float]]:
    return [r for r in rows if t_start <= r["t_s"] <= t_end]


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


def locate_active_mean_mw(
    rows: list[dict[str, float]],
    *,
    locate_window_s: float,
) -> tuple[float, float]:
    """Return (max sliding mean power mW, window start t_s)."""
    if not rows:
        return 0.0, 0.0
    best_mean = 0.0
    best_t = rows[0]["t_s"]
    for row in rows:
        t0 = row["t_s"]
        seg = slice_rows_by_time(rows, t0, t0 + locate_window_s)
        if len(seg) < 2:
            continue
        m = mean_power_mw(seg)
        if m > best_mean:
            best_mean = m
            best_t = t0
    return best_mean, best_t


def integrate_batch_energy(
    rows: list[dict[str, float]],
    *,
    p_static_mw: float,
    batch_duration_ms: float,
    batch_windows: int,
    locate_window_s: float = 10.0,
    batch_start_s: float | None = None,
) -> dict[str, float]:
    """
    Integrate only over the measured batch duration (from board_bench.txt).

    At ~100 Hz the 926 µs DMA burst is undersampled; we scale by batch_duration_ms
    rather than integrating the full 30 s log. Dynamic increment uses the peak
    sliding mean during the bench activity window.
    """
    if batch_duration_ms <= 0:
        raise ValueError("batch_duration_ms must be positive for batch integration")
    if batch_windows <= 0:
        raise ValueError("batch_windows must be positive")

    batch_s = batch_duration_ms / 1000.0

    if batch_start_s is not None:
        active_mean = mean_power_mw(slice_rows_by_time(rows, batch_start_s, batch_start_s + locate_window_s))
        active_t = batch_start_s
    else:
        active_mean, active_t = locate_active_mean_mw(rows, locate_window_s=locate_window_s)

    e_total_mj = p_static_mw * batch_s
    p_excess = max(0.0, active_mean - p_static_mw)
    e_dynamic_mj = p_excess * batch_s

    return {
        "batch_duration_ms": batch_duration_ms,
        "batch_start_s": active_t,
        "active_mean_mw": active_mean,
        "p_static_mw": p_static_mw,
        "e_total_mj": e_total_mj,
        "e_dynamic_mj": e_dynamic_mj,
        "e_total_per_window_uj": e_total_mj * 1000.0 / batch_windows,
        "e_dynamic_per_window_uj": e_dynamic_mj * 1000.0 / batch_windows,
    }


def write_summary(
    path: Path,
    *,
    shunt_mohm: float,
    v_rail: float,
    batch_windows: int,
    p_static_mw: float,
    e_dynamic_mj: float,
    batch_duration_ms: float,
    e_total_mj: float | None = None,
    e_total_per_window_uj: float | None = None,
    e_dynamic_per_window_uj: float | None = None,
    integrate_mode: str = "batch",
    notes: str = "",
) -> None:
    if e_dynamic_per_window_uj is None:
        e_dynamic_per_window_uj = (e_dynamic_mj * 1000.0 / batch_windows) if batch_windows else 0.0
    if e_total_mj is None:
        e_total_mj = p_static_mw * (batch_duration_ms / 1000.0)
    if e_total_per_window_uj is None:
        e_total_per_window_uj = e_total_mj * 1000.0 / batch_windows if batch_windows else 0.0

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
Integrate:    {integrate_mode}

Batch inference (DMA stream path)
---------------------------------
Batch windows:      {batch_windows}
Batch duration (ms): {batch_duration_ms:.3f}
Static power (mW):  {p_static_mw:.3f}
Total batch energy (mJ): {e_total_mj:.6f}
Dynamic increment (mJ): {e_dynamic_mj:.6f}
Total energy per window (uJ): {e_total_per_window_uj:.3f}
Dynamic energy per window (uJ): {e_dynamic_per_window_uj:.6f}

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
    parser.add_argument(
        "--integrate-mode",
        choices=("batch", "full"),
        default="batch",
        help="batch=scale by batch_duration_ms (default); full=legacy 30s log integral",
    )
    parser.add_argument(
        "--batch-locate-window-s",
        type=float,
        default=10.0,
        help="Sliding window (s) to find peak bench activity mean power",
    )
    parser.add_argument(
        "--batch-start-s",
        type=float,
        default=None,
        help="Optional bench start time (s) within batch CSV; auto-locate if omitted",
    )
    parser.add_argument("--summary-out", type=Path, default=REPO / "results" / "phase3" / "energy_batch.txt")
    parser.add_argument(
        "--cal-gain",
        type=float,
        default=None,
        help="Scale shunt/current/power (J21 wire fix). Default 1; or env INA219_CAL_GAIN",
    )
    parser.add_argument(
        "--cal-ref-mv",
        type=float,
        default=None,
        help="Multimeter mV on J21 at idle; auto-computes gain at log start (env INA219_CAL_REF_MV)",
    )
    parser.add_argument(
        "--cal-settle-s",
        type=float,
        default=0.5,
        help="Seconds to average raw shunt before --cal-ref-mv gain (default 0.5)",
    )
    parser.add_argument("--notes", type=str, default="", help="Extra notes for summary output")
    args = parser.parse_args()

    env_gain = os.environ.get("INA219_CAL_GAIN")
    if args.cal_gain is None and env_gain:
        args.cal_gain = float(env_gain)
    env_ref = os.environ.get("INA219_CAL_REF_MV")
    if args.cal_ref_mv is None and env_ref:
        args.cal_ref_mv = float(env_ref)

    if args.integrate:
        rows = load_csv(args.integrate)
        if args.cal_gain is not None and args.cal_gain != 1.0:
            rows = [apply_cal_gain(r, args.cal_gain) for r in rows]
        if args.static_csv and args.cal_gain is not None and args.cal_gain != 1.0:
            static_rows = load_csv(args.static_csv)
            static_rows = [apply_cal_gain(r, args.cal_gain) for r in static_rows]
        else:
            static_rows = None
        if args.static_mw is not None:
            p_static = args.static_mw
        elif args.static_csv:
            p_static = mean_power_mw(static_rows if static_rows is not None else load_csv(args.static_csv))
        else:
            p_static = mean_power_mw(rows[: max(1, int(0.1 * len(rows)))])
            print(f"Warning: no static baseline; using first 10% mean = {p_static:.3f} mW")

        batch_ms = args.batch_duration_ms
        if batch_ms <= 0:
            bench_txt = REPO / "results" / "phase3" / "board_bench.txt"
            if bench_txt.exists():
                for line in bench_txt.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("total") and "us" in line:
                        us = float(line.split("=")[1].strip().split()[0])
                        batch_ms = us / 1000.0
                        print(f"Using batch duration from {bench_txt}: {batch_ms:.3f} ms")
                        break
        if batch_ms <= 0:
            print("ERROR: set --batch-duration-ms or ensure results/phase3/board_bench.txt has total=...us")
            return 1

        if args.integrate_mode == "full":
            e_dyn = integrate_energy_mj(rows, p_static)
            batch_ms_out = batch_ms
            e_total_mj = None
            e_total_uj = None
            e_dyn_uj = e_dyn * 1000.0 / args.batch_windows if args.batch_windows else 0.0
            mode_note = "integrate_mode=full (legacy 30s log)"
        else:
            result = integrate_batch_energy(
                rows,
                p_static_mw=p_static,
                batch_duration_ms=batch_ms,
                batch_windows=args.batch_windows,
                locate_window_s=args.batch_locate_window_s,
                batch_start_s=args.batch_start_s,
            )
            e_dyn = result["e_dynamic_mj"]
            batch_ms_out = result["batch_duration_ms"]
            e_total_mj = result["e_total_mj"]
            e_total_uj = result["e_total_per_window_uj"]
            e_dyn_uj = result["e_dynamic_per_window_uj"]
            mode_note = (
                f"integrate_mode=batch locate@{result['batch_start_s']:.2f}s "
                f"active_mean={result['active_mean_mw']:.1f}mW"
            )

        cal_note = ""
        if args.cal_gain is not None and args.cal_gain != 1.0:
            cal_note = f" cal_gain={args.cal_gain:g}x"
        elif args.cal_ref_mv is not None:
            cal_note = f" cal_ref_mv={args.cal_ref_mv:g}"
        extra = args.notes.strip()
        notes = f"Integrated from {args.integrate}.{mode_note}.{cal_note}"
        if extra:
            notes = f"{notes} {extra}"
        write_summary(
            args.summary_out,
            shunt_mohm=args.shunt_mohm,
            v_rail=args.v_rail,
            batch_windows=args.batch_windows,
            p_static_mw=p_static,
            e_dynamic_mj=e_dyn,
            batch_duration_ms=batch_ms_out,
            e_total_mj=e_total_mj,
            e_total_per_window_uj=e_total_uj,
            e_dynamic_per_window_uj=e_dyn_uj,
            integrate_mode=args.integrate_mode,
            notes=notes,
        )
        return 0

    ina = INA219(args.bus, args.address, args.shunt_mohm)
    try:
        cal_gain = resolve_cal_gain(
            args.cal_gain,
            args.cal_ref_mv,
            ina,
            settle_s=args.cal_settle_s,
            rate_hz=args.rate_hz,
        )
    except SystemExit:
        ina.close()
        raise

    print("INA219 logger")
    print(f"  bus={args.bus} addr=0x{args.address:02x} shunt={args.shunt_mohm} mOhm")
    if cal_gain != 1.0:
        print(f"  cal_gain={cal_gain:.3f}x (applied to shunt/current/power)")
    print(f"  duration={args.duration}s @ {args.rate_hz} Hz")
    print(f"  output={args.out}")
    print()

    try:
        log_samples(ina, args.duration, args.rate_hz, args.out, cal_gain=cal_gain)
    finally:
        ina.close()

    rows = load_csv(args.out)
    print(f"Logged {len(rows)} samples. Mean power = {mean_power_mw(rows):.3f} mW")
    print("Next: run batch bench during a second log, then --integrate with --static-csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
