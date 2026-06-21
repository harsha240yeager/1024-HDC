#!/usr/bin/env python3
"""
Export a subset of EMG inference windows for on-board replay (Phase 3).

Usage (from repo root):
  python3 scripts/export_emg_board_vectors.py [--max-windows N] [--out sw/emg_board_vectors.h]

Requires python_ref EMG baseline artifacts and HDC-EMG clone — see python_ref/README.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export EMG board vectors (Phase 3 scaffold)")
    parser.add_argument("--max-windows", type=int, default=1000, help="Max windows to export")
    parser.add_argument("--out", type=Path, default=REPO / "sw" / "emg_board_vectors.h")
    args = parser.parse_args()

    print("Phase 3 EMG board export — scaffold")
    print(f"  repo:        {REPO}")
    print(f"  max_windows: {args.max_windows}")
    print(f"  output:      {args.out}")
    print()
    print("TODO: wire to python_ref/hdc_ref.py EMG encode + classify pipeline.")
    print("      Then rebuild sw/hdc_emg_board_test.c with EMG_BOARD_WINDOWS > 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
