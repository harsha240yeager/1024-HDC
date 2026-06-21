#!/usr/bin/env python3
"""
Log INA219 power during Phase 3 batch bench (scaffold).

Usage:
  python3 scripts/ina219_log.py --duration 30 --out results/phase3/logs/ina219.csv

Requires: pip install smbus2 (or adafruit-circuitpython-ina219 on host with I2C).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="INA219 logger for Phase 3 energy")
    parser.add_argument("--duration", type=float, default=30.0, help="Seconds to log")
    parser.add_argument("--rate-hz", type=float, default=100.0, help="Sample rate")
    parser.add_argument("--out", type=Path, default=REPO / "results" / "phase3" / "logs" / "ina219.csv")
    args = parser.parse_args()

    print("Phase 3 INA219 logger — scaffold")
    print(f"  duration: {args.duration}s @ {args.rate_hz} Hz")
    print(f"  output:   {args.out}")
    print()
    print("TODO: open I2C bus, read INA219 power register, write CSV with timestamps.")
    print("      Run concurrently with: bash board/HDC_DMA/run_batch_bench.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
