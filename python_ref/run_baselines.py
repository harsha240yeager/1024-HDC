#!/usr/bin/env python3
"""Run Tier 4 comparison baselines (MLP + ARM HDC)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def main() -> int:
    p = argparse.ArgumentParser(description="Run all Tier 4 baselines")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--mlp-only", action="store_true")
    p.add_argument("--arm-only", action="store_true")
    args = p.parse_args()

    extra = ["--quick"] if args.quick else []
    scripts = []
    if not args.arm_only:
        scripts.append("run_mlp_baseline.py")
    if not args.mlp_only:
        scripts.append("run_arm_hdc_baseline.py")

    for name in scripts:
        cmd = [sys.executable, str(HERE / name), *extra]
        print(f"\n>>> {' '.join(cmd)}\n", flush=True)
        subprocess.run(cmd, check=True, cwd=str(REPO))

    print("\nAll baselines complete. See results/baselines/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
