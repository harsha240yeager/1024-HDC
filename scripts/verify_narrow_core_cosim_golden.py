#!/usr/bin/env python3
"""Golden-model checks for #29 step 5 (identity + narrow) without a simulator.

1. Identity: K=D, SEL[i]=i narrow export must match baseline all-ones export.
2. Narrow: K=128 gathered export class/dist must match masked full-width classify
   on the same encoded windows (bit-exact property from Option E).

Usage:
  python3 scripts/verify_narrow_core_cosim_golden.py
  python3 scripts/verify_narrow_core_cosim_golden.py --count 500 --seed 31
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "python_ref"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bundle_majority,
    export_core_cosim,
    export_narrow_core_cosim,
    gather_narrow_bits,
    hamming,
)

KEEP_TO_NPZ_KEY = {0.125: "mask_keep_0_125", 0.5: "mask_keep_0_5", 1.0: "mask_keep_1_0"}


def _parse_expect(path: Path) -> list[tuple[int, int]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        word = int(line, 16)
        rows.append(((word >> 16) & 0xFFFF, word & 0xFFFF))
    return rows


def check_identity(cfg: HDCConfig, count: int, seed: int) -> bool:
    sel = np.arange(cfg.D, dtype=np.int64)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        export_narrow_core_cosim(root / "narrow", cfg, count, seed, sel, n_class=8)
        export_core_cosim(root / "base", cfg, count, seed, n_class=8, allones_mask=True)
        narrow = _parse_expect(root / "narrow" / "core_expect.hex")
        base = _parse_expect(root / "base" / "core_expect.hex")
    mism = sum(1 for a, b in zip(narrow, base) if a != b)
    ok = mism == 0
    print(f"identity: {count - mism}/{count} cases match baseline all-ones ({'PASS' if ok else 'FAIL'})")
    return ok


def check_narrow_masked(cfg: HDCConfig, count: int, seed: int, sel: np.ndarray, mask: np.ndarray) -> bool:
    rng = np.random.default_rng(seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    n_class = 8
    train_per_class = 5
    n_ch, n_ft = cfg.n_channels, cfg.n_features

    protos = np.zeros((n_class, cfg.D), dtype=np.uint8)
    for k in range(n_class):
        windows = [
            engine.encode_emg_window(
                rng.integers(0, cfg.n_levels, size=(n_ch, n_ft), dtype=np.int32), mem
            )
            for _ in range(train_per_class)
        ]
        protos[k] = bundle_majority(windows, cfg)
    protos_n = np.stack([gather_narrow_bits(protos[k], sel) for k in range(n_class)])

    dist_mism = pred_mism = 0
    for _ in range(count):
        q = rng.integers(0, cfg.n_levels, size=(n_ch, n_ft), dtype=np.int32)
        query = engine.encode_emg_window(q, mem)
        q_n = gather_narrow_bits(query, sel)
        d_full = np.array([hamming(query, protos[k], mask=mask) for k in range(n_class)], dtype=np.int32)
        d_narrow = np.array([hamming(q_n, protos_n[k]) for k in range(n_class)], dtype=np.int32)
        if not np.array_equal(d_full, d_narrow):
            dist_mism += 1
        if int(d_full.argmin()) != int(d_narrow.argmin()):
            pred_mism += 1

    ok = dist_mism == 0 and pred_mism == 0
    print(
        f"narrow K={sel.size}: dist mismatches={dist_mism} pred mismatches={pred_mism} "
        f"over {count} windows ({'PASS' if ok else 'FAIL'})"
    )
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify narrow co-sim golden model (#29 step 5)")
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--keep", type=float, default=0.125)
    ap.add_argument("--manifest", type=Path, default=REPO / "results/narrow_rtl/sel_table_manifest.json")
    ap.add_argument("--mask-npz", type=Path, default=REPO / "results/protocol_v2/fisher_pooled.npz")
    args = ap.parse_args()

    cfg = HDCConfig(D=1024, words=16, bits_per_word=64, seed=args.seed)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sel = np.asarray(manifest["sel"], dtype=np.int64)

    key = KEEP_TO_NPZ_KEY.get(args.keep)
    if key is None:
        raise SystemExit(f"unsupported keep={args.keep}")
    mask = np.asarray(np.load(args.mask_npz)[key]).astype(np.uint8)

    ok_id = check_identity(cfg, args.count, args.seed)
    ok_narrow = check_narrow_masked(cfg, args.count, args.seed, sel, mask)
    return 0 if (ok_id and ok_narrow) else 1


if __name__ == "__main__":
    raise SystemExit(main())
