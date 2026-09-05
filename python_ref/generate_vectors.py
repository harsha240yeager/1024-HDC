#!/usr/bin/env python3
"""Generate co-simulation vectors for ModelSim/Questa.

Formats:
  * default (per-case): one directory per case (in_vec.hex, bind_vec.hex,
    expected.hex, ctrl.txt) plus manifest.json.
  * --flat: a single flat, $readmemh-friendly bind+permute set (in_vec.hex,
    bind_vec.hex, expected.hex, ctrl.hex, meta.txt) for tb/tb_cosim.sv.
  * --bundle: a flat bundle set (bundle_in.hex, expected.hex, kcnt.hex,
    meta.txt) for tb/tb_bundle_cosim.sv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from hdc_ref import (
    HDCConfig,
    export_am_cosim,
    export_bind_permute_cosim,
    export_bind_permute_vectors,
    export_bundle_cosim,
    export_core_cosim,
    export_encoder_cosim,
    export_narrow_core_cosim,
    export_pruning_mask_cosim,
)

KEEP_TO_NPZ_KEY = {1.0: "mask_keep_1_0", 0.5: "mask_keep_0_5", 0.125: "mask_keep_0_125"}


def _load_fisher_mask(npz_path: Path, keep: float) -> np.ndarray:
    key = KEEP_TO_NPZ_KEY.get(keep)
    if key is None:
        raise SystemExit(f"keep={keep} not in frozen artefact keys {sorted(KEEP_TO_NPZ_KEY)}")
    data = np.load(npz_path)
    if key not in data:
        raise SystemExit(f"{npz_path} missing {key}")
    return np.asarray(data[key]).astype(np.uint8)


def main() -> None:
    p = argparse.ArgumentParser(description="Export HDC golden vectors for RTL co-simulation")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="output directory (defaults depend on format)")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--D", type=int, default=1024)
    p.add_argument("--flat", action="store_true",
                   help="emit flat bind+permute $readmemh files for tb_cosim.sv")
    p.add_argument("--bundle", action="store_true",
                   help="emit flat bundle $readmemh files for tb_bundle_cosim.sv")
    p.add_argument("--am", action="store_true",
                   help="emit flat associative-memory $readmemh files for tb_am_cosim.sv")
    p.add_argument("--pruning-mask", dest="pruning_mask", action="store_true",
                   help="emit pruning-mask $readmemh files for tb_pruning_mask_cosim.sv")
    p.add_argument("--encoder", action="store_true",
                   help="emit encoder $readmemh files + item_mem .mem for tb_encoder_cosim.sv")
    p.add_argument("--core", action="store_true",
                   help="emit end-to-end core $readmemh files for tb_core_cosim.sv")
    p.add_argument("--narrow-core", action="store_true",
                   help="emit narrow-core vectors for tb_core_narrow_cosim.sv")
    p.add_argument("--identity-sel", action="store_true",
                   help="with --narrow-core: K=D and SEL[i]=i (identity regression pass)")
    p.add_argument("--keep", type=float, default=0.125,
                   help="with --narrow-core: Fisher keep ratio for SEL (default 0.125)")
    p.add_argument("--sel-manifest", type=Path,
                   default=Path("results/narrow_rtl/sel_table_manifest.json"),
                   help="manifest with sel[] for --narrow-core")
    p.add_argument("--mask-npz", type=Path,
                   default=Path("results/protocol_v2/fisher_pooled.npz"))
    p.add_argument("--kmin", type=int, default=2, help="bundle: min vectors per case")
    p.add_argument("--kmax", type=int, default=16, help="bundle: max vectors per case")
    p.add_argument("--cnt-bits", type=int, default=6, help="bundle: counter width")
    p.add_argument("--nclass", type=int, default=8, help="AM: number of class prototypes")
    args = p.parse_args()

    bits_per_word = 64
    if args.D % bits_per_word != 0:
        p.error(f"--D ({args.D}) must be a multiple of {bits_per_word}")
    cfg = HDCConfig(D=args.D, words=args.D // bits_per_word,
                    bits_per_word=bits_per_word, seed=args.seed)

    if args.narrow_core:
        repo = Path(__file__).resolve().parents[1]
        manifest_path = args.sel_manifest
        if not manifest_path.is_absolute():
            manifest_path = repo / manifest_path
        npz_path = args.mask_npz
        if not npz_path.is_absolute():
            npz_path = repo / npz_path

        out_dir = args.out_dir or Path("vectors/cosim_core_narrow")
        if args.identity_sel:
            sel = np.arange(cfg.D, dtype=np.int64)
            mask = None
        else:
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                sel = np.asarray(manifest["sel"], dtype=np.int64)
            else:
                mask_arr = _load_fisher_mask(npz_path, args.keep)
                sel = np.flatnonzero(mask_arr).astype(np.int64)
            mask = _load_fisher_mask(npz_path, args.keep) if npz_path.is_file() else None
        meta = export_narrow_core_cosim(
            out_dir, cfg, args.count, args.seed, sel, n_class=args.nclass, mask=mask
        )
        print(
            f"Wrote {meta['count']} narrow-core cases (K={meta['k_bits']}, "
            f"{meta['n_channels']}x{meta['n_features']} pairs, n_class={meta['n_class']}) "
            f"to {out_dir.resolve()}"
        )
    elif args.core:
        out_dir = args.out_dir or Path("vectors/cosim_core")
        meta = export_core_cosim(out_dir, cfg, args.count, args.seed, n_class=args.nclass)
        print(f"Wrote {meta['count']} core cases (D={meta['D']}, "
              f"{meta['n_channels']}x{meta['n_features']} pairs, "
              f"n_class={meta['n_class']}, mask_density={meta['mask_density']:.3f}) "
              f"to {out_dir.resolve()}")
    elif args.encoder:
        out_dir = args.out_dir or Path("vectors/cosim_encoder")
        meta = export_encoder_cosim(out_dir, cfg, args.count, args.seed)
        print(f"Wrote {meta['count']} encoder cases (D={meta['D']}, "
              f"{meta['n_channels']}x{meta['n_features']} pairs, "
              f"n_levels={meta['n_levels']}) to {out_dir.resolve()}")
    elif args.am:
        out_dir = args.out_dir or Path("vectors/cosim_am")
        meta = export_am_cosim(out_dir, cfg, args.count, args.seed, n_class=args.nclass)
        print(f"Wrote {meta['count']} AM cases (D={meta['D']}, "
              f"n_class={meta['n_class']}) to {out_dir.resolve()}")
    elif args.pruning_mask:
        out_dir = args.out_dir or Path("vectors/cosim_pruning_mask")
        meta = export_pruning_mask_cosim(out_dir, cfg, args.count, args.seed)
        print(f"Wrote {meta['count']} pruning-mask cases (D={meta['D']}, "
              f"axi_words={meta['axi_words']}) to {out_dir.resolve()}")
    elif args.bundle:
        out_dir = args.out_dir or Path("vectors/cosim_bundle")
        meta = export_bundle_cosim(
            out_dir, cfg, args.count, args.seed,
            k_min=args.kmin, k_max=args.kmax, cnt_bits=args.cnt_bits,
        )
        print(f"Wrote {meta['count']} bundle cases (D={meta['D']}, "
              f"K in [{meta['k_min']},{meta['k_max']}], cnt_bits={meta['cnt_bits']}) "
              f"to {out_dir.resolve()}")
    elif args.flat:
        out_dir = args.out_dir or Path("vectors/cosim")
        meta = export_bind_permute_cosim(out_dir, cfg, args.count, args.seed)
        print(f"Wrote {meta['count']} flat cases (D={meta['D']}) to {out_dir.resolve()}")
    else:
        out_dir = args.out_dir or Path("vectors")
        export_bind_permute_vectors(out_dir, cfg, args.count, args.seed)
        print(f"Wrote {args.count} cases to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
