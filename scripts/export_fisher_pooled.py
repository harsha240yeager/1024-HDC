#!/usr/bin/env python3
"""Export pooled Fisher scores + informed masks for heatmap (silicon path).

Writes results/hook_a/fisher_pooled.npz (scores, mask at keep 1.0/0.5/0.125).
Reuses the same TRAIN encoding path as patch_emg_anchor.py (pooled over subjects).

Usage:
  python3 scripts/export_fisher_pooled.py
  python3 scripts/export_fisher_pooled.py --max-train-windows 5000   # dev sample
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.io as sio

REPO = Path(__file__).resolve().parents[1]
PYREF = REPO / "python_ref"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PYREF))

from hdc_ref import HDCConfig, HDCEngine, ItemMemory, mask_from_scores, per_bit_fisher_scores  # noqa: E402
from scripts.export_emg_board_vectors import (  # noqa: E402
    DATASET,
    level21_to_grid,
    quantize_envelope,
    split_train_test,
)

DEFAULT_CONFIG = REPO / "python_ref/config/emg_baseline.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--max-train-windows", type=int, default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO / "results/hook_a/fisher_pooled.npz",
    )
    args = ap.parse_args()

    cfg_json = json.loads(args.config.read_text(encoding="utf-8"))
    cfg = HDCConfig(D=1024, seed=int(cfg_json.get("item_mem_seed", 42)))
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    subjects = cfg_json["dataset"]["subjects"]

    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    train_hvs = []
    train_labels = []

    print("Encoding pooled TRAIN windows for Fisher scores ...")
    for subject in subjects:
        mat = sio.loadmat(str(DATASET))
        data = mat[f"COMPLETE_{subject}"].astype(np.float64)
        labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
        q_all = quantize_envelope(data)
        train_q, train_y, _, _ = split_train_test(q_all, labels, train_frac, seed)
        n = train_q.shape[0]
        if args.max_train_windows is not None:
            n = min(n, args.max_train_windows)
        print(f"  subject {subject}: {n} train windows", flush=True)
        for i in range(n):
            if i > 0 and i % 5000 == 0:
                print(f"    {i}/{n}", flush=True)
            grid = level21_to_grid(train_q[i], cfg)
            train_hvs.append(engine.encode_emg_window(grid, mem))
            train_labels.append(int(train_y[i]))

    scores = per_bit_fisher_scores(np.stack(train_hvs), np.array(train_labels, dtype=np.int32))
    masks = {
        "keep_1.0": np.ones(cfg.D, dtype=np.uint8),
        "keep_0.5": mask_from_scores(scores, 0.5, informed=True),
        "keep_0.125": mask_from_scores(scores, 0.125, informed=True),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.out,
        scores=scores,
        mask_keep_1_0=masks["keep_1.0"],
        mask_keep_0_5=masks["keep_0.5"],
        mask_keep_0_125=masks["keep_0.125"],
        D=cfg.D,
        subjects=np.array(subjects),
    )
    print(
        f"Wrote {args.out}  scores [{scores.min():.3g}, {scores.max():.3g}]  "
        f"keep@0.5={int(masks['keep_0.5'].sum())}  keep@0.125={int(masks['keep_0.125'].sum())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
