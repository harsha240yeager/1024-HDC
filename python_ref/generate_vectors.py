#!/usr/bin/env python3
"""Generate bind+permute co-simulation vectors for ModelSim."""

from __future__ import annotations

import argparse
from pathlib import Path

from hdc_ref import HDCConfig, export_bind_permute_vectors


def main() -> None:
    p = argparse.ArgumentParser(description="Export HDC golden vectors for RTL co-simulation")
    p.add_argument("--out-dir", type=Path, default=Path("vectors"))
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--D", type=int, default=1024)
    args = p.parse_args()

    cfg = HDCConfig(D=args.D, seed=args.seed)
    export_bind_permute_vectors(args.out_dir, cfg, args.count, args.seed)
    print(f"Wrote {args.count} cases to {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
