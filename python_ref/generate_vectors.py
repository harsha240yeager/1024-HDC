#!/usr/bin/env python3
"""Generate bind+permute co-simulation vectors for ModelSim/Questa.

Two output formats:
  * default (per-case): one directory per case (in_vec.hex, bind_vec.hex,
    expected.hex, ctrl.txt) plus manifest.json.
  * --flat: a single flat, $readmemh-friendly set (in_vec.hex, bind_vec.hex,
    expected.hex, ctrl.hex, meta.txt) consumed by tb/tb_cosim.sv.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from hdc_ref import (
    HDCConfig,
    export_bind_permute_cosim,
    export_bind_permute_vectors,
)


def main() -> None:
    p = argparse.ArgumentParser(description="Export HDC golden vectors for RTL co-simulation")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="output directory (default: vectors, or vectors/cosim with --flat)")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--D", type=int, default=1024)
    p.add_argument("--flat", action="store_true",
                   help="emit flat $readmemh files for tb_cosim.sv")
    args = p.parse_args()

    cfg = HDCConfig(D=args.D, seed=args.seed)

    if args.flat:
        out_dir = args.out_dir or Path("vectors/cosim")
        meta = export_bind_permute_cosim(out_dir, cfg, args.count, args.seed)
        print(f"Wrote {meta['count']} flat cases (D={meta['D']}) to {out_dir.resolve()}")
    else:
        out_dir = args.out_dir or Path("vectors")
        export_bind_permute_vectors(out_dir, cfg, args.count, args.seed)
        print(f"Wrote {args.count} cases to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
