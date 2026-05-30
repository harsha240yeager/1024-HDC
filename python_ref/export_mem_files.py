#!/usr/bin/env python3
"""Export item-memory .mem files and example pruning masks."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from hdc_ref import HDCConfig, ItemMemory, export_pruning_mask_hex, make_pruning_masks


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", type=Path, default=Path("mem_files"))
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    cfg = HDCConfig(seed=args.seed)
    mem = ItemMemory(cfg)
    mem.export_mem_files(args.out_dir)

    # Example pruning masks at 50% keep (synthetic labels for demo)
    rng = np.random.default_rng(0)
    n = 60
    q = np.stack([rng.integers(0, 2, cfg.D, dtype=np.uint8) for _ in range(n)], axis=0)
    y = rng.integers(0, 5, size=n, dtype=np.int32)
    informed, random_m = make_pruning_masks(q, y, keep_ratio=0.5, cfg=cfg, random_seed=1)

    export_pruning_mask_hex(informed, args.out_dir / "pruning_mask_informed.mem", cfg)
    export_pruning_mask_hex(random_m, args.out_dir / "pruning_mask_random.mem", cfg)

    print(f"Exported item memories + example masks to {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
