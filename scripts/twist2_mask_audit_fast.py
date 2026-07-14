#!/usr/bin/env python3
"""
Fast Twist 2 mask audit — verify local vs pooled Fisher masks differ but can tie on accuracy.

Subsamples windows per subject for minutes-scale runtime. Full Twist 2 sweeps use all windows
and train S1–18 for the pooled mask; this script defaults to S1–3 for pooled mask speed.

Usage (repo root):
  python3 scripts/twist2_mask_audit_fast.py
  python3 scripts/twist2_mask_audit_fast.py --out results/twist2_36_keep05/mask_audit_fast.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import scipy.io as sio

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python_ref"))
sys.path.insert(0, str(REPO / "scripts"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bundle_majority_unlimited,
    mask_from_scores,
    per_bit_fisher_scores,
)
from export_emg_board_vectors import level21_to_grid, quantize_envelope, split_train_test  # noqa: E402

SEED = 42
TRAIN_FRAC = 0.2
MAX_TRAIN = 1000
MAX_TEST = 2000
DATASET5 = REPO / "python_ref/HDC-EMG/dataset.mat"
DATASET36 = REPO / "python_ref/HDC-EMG/dataset_36.mat"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fast Twist 2 local vs pooled mask audit")
    p.add_argument(
        "--out",
        type=Path,
        default=REPO / "results/twist2_36_keep05/mask_audit_fast.json",
    )
    return p.parse_args()


def load_sub(sid: int, dataset: Path, max_train: int, max_test: int):
    mat = sio.loadmat(str(dataset))
    data = mat[f"COMPLETE_{sid}"].astype(np.float64)
    labels = mat[f"LABEL_{sid}"].ravel().astype(np.int64)
    q = quantize_envelope(data)
    tr_q, tr_l, te_q, te_l = split_train_test(q, labels, TRAIN_FRAC, SEED)
    return tr_q[:max_train], tr_l[:max_train], te_q[:max_test], te_l[:max_test]


def encode_q(engine: HDCEngine, mem: ItemMemory, cfg: HDCConfig, q: np.ndarray) -> np.ndarray:
    return np.array(
        [
            engine.encode_emg_window(level21_to_grid(q[i], cfg), mem, cnt_bits=6)
            for i in range(len(q))
        ],
        dtype=np.uint8,
    )


def build_pooled_mask(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    train_subs: list[int],
    dataset: Path,
    keep: float,
    max_train: int,
) -> np.ndarray:
    parts_h, parts_l = [], []
    for s in train_subs:
        tq, tl, _, _ = load_sub(s, dataset, max_train, MAX_TEST)
        parts_h.append(encode_q(engine, mem, cfg, tq))
        parts_l.append(tl)
    ph = np.vstack(parts_h)
    pl = np.concatenate(parts_l).astype(np.int32)
    return mask_from_scores(per_bit_fisher_scores(ph, pl), keep, informed=True)


def protos_from_train(
    engine: HDCEngine, mem: ItemMemory, cfg: HDCConfig, tr_q: np.ndarray, tr_l: np.ndarray
) -> np.ndarray:
    protos = np.zeros((5, cfg.D), dtype=np.uint8)
    for k in range(1, 6):
        idx = np.where(tr_l == k)[0]
        wins = [
            engine.encode_emg_window(level21_to_grid(tr_q[i], cfg), mem, cnt_bits=6) for i in idx
        ]
        protos[k - 1] = bundle_majority_unlimited(wins, cfg)
    return protos


def accuracy(
    engine: HDCEngine, te_h: np.ndarray, te_l: np.ndarray, protos: np.ndarray, m_arr: np.ndarray
) -> tuple[float, int, int]:
    gt = te_l.astype(np.int32) - 1
    correct = 0
    for i in range(len(te_l)):
        pred = engine.classify(te_h[i], protos, mask=m_arr).class_id
        if pred == int(gt[i]):
            correct += 1
    n = len(te_l)
    return 100.0 * correct / n, correct, n


def run_case(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    name: str,
    dataset: Path,
    train_subs: list[int],
    test_sid: int,
    keep: float,
    max_train: int,
    max_test: int,
) -> dict:
    tr_q, tr_l, te_q, te_l = load_sub(test_sid, dataset, max_train, max_test)
    tr_h = encode_q(engine, mem, cfg, tr_q)
    te_h = encode_q(engine, mem, cfg, te_q)
    local_m = mask_from_scores(
        per_bit_fisher_scores(tr_h, tr_l.astype(np.int32)), keep, informed=True
    )
    pool_m = build_pooled_mask(engine, mem, cfg, train_subs, dataset, keep, max_train)
    full_m = np.ones(cfg.D, dtype=np.uint8)
    protos = protos_from_train(engine, mem, cfg, tr_q, tr_l)
    au, cu, n = accuracy(engine, te_h, te_l, protos, full_m)
    al, cl, _ = accuracy(engine, te_h, te_l, protos, local_m)
    ap, cp, _ = accuracy(engine, te_h, te_l, protos, pool_m)
    overlap = int((local_m & pool_m).sum())
    union = int((local_m | pool_m).sum())
    return {
        "case": name,
        "test_subject": test_sid,
        "keep_ratio": keep,
        "n_keep": int(pool_m.sum()),
        "masks_identical": bool(np.array_equal(local_m, pool_m)),
        "mask_overlap_bits": overlap,
        "mask_jaccard": round(overlap / union, 4) if union else 1.0,
        "unpruned_accuracy": round(au, 4),
        "local_oracle_accuracy": round(al, 4),
        "pooled_transfer_accuracy": round(ap, 4),
        "gap_local_minus_pooled_pp": round(al - ap, 4),
        "local_lossless": cl == cu,
        "pooled_lossless": cp == cu,
        "same_predictions": cl == cp,
        "test_windows_subsampled": n,
    }


def main() -> int:
    args = parse_args()
    cfg = HDCConfig(D=1024, words=16, bits_per_word=64, seed=42)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    train_fast = [1, 2, 3]

    cases = [
        run_case(engine, mem, cfg, "pilot S4", DATASET5, train_fast, 4, 0.125, MAX_TRAIN, MAX_TEST),
        run_case(engine, mem, cfg, "pilot S5", DATASET5, train_fast, 5, 0.125, MAX_TRAIN, MAX_TEST),
        run_case(
            engine,
            mem,
            cfg,
            "36-subject S19 keep0.125",
            DATASET36,
            train_fast,
            19,
            0.125,
            MAX_TRAIN,
            MAX_TEST,
        ),
        run_case(
            engine,
            mem,
            cfg,
            "36-subject S19 keep0.5",
            DATASET36,
            train_fast,
            19,
            0.5,
            MAX_TRAIN,
            MAX_TEST,
        ),
        run_case(
            engine,
            mem,
            cfg,
            "36-subject S34 keep0.5",
            DATASET36,
            train_fast,
            34,
            0.5,
            MAX_TRAIN,
            MAX_TEST,
        ),
    ]
    payload = {
        "description": "Fast Twist 2 mask audit: local vs pooled Fisher masks on subsampled windows.",
        "method": f"Max {MAX_TRAIN} train / {MAX_TEST} test windows; pooled mask from S1–3 (audit speed).",
        "note": "Full 36-subject sweeps pool Fisher scores from train S1–18 over all TRAIN windows.",
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for c in cases:
        print(
            f"{c['case']}: identical={c['masks_identical']} jaccard={c['mask_jaccard']} "
            f"gap={c['gap_local_minus_pooled_pp']:+.2f} pp pooled_lossless={c['pooled_lossless']}"
        )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
