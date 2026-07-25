#!/usr/bin/env python3
"""
Audit train/test split for Protocol HDC-1 vs HDC-2.

Gate for DATE major revision Phase 1: overlap must be 0 under HDC-2.

Usage (repo root):
  python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline_v2.json
  python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline.json
  python scripts/audit_split_leakage.py --synthetic-only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List

import numpy as np
import scipy.io as sio

REPO = Path(__file__).resolve().parents[1]
PYREF = REPO / "python_ref"
sys.path.insert(0, str(PYREF))
sys.path.insert(0, str(REPO / "scripts"))

from export_emg_board_vectors import (  # noqa: E402
    DATASET,
    compute_train_indices,
    compute_test_indices,
    load_config,
    protocol_test_set,
    quantize_envelope,
    require_dataset,
    split_kwargs_from_config,
    split_train_test,
)


def audit_subject(
    labels: np.ndarray,
    train_frac: float,
    seed: int,
    split_kw: dict,
) -> dict:
    n = int(labels.shape[0])
    train_idx = compute_train_indices(labels, train_frac, seed)
    test_set = split_kw.get("test_set", "full_recording")
    if test_set == "disjoint":
        test_idx = compute_test_indices(
            labels, train_idx, boundary_gap=int(split_kw.get("boundary_gap", 0))
        )
    else:
        test_idx = np.arange(n, dtype=np.int64)

    train_set = set(int(i) for i in train_idx.tolist())
    test_set_idx = set(int(i) for i in test_idx.tolist())
    overlap = sorted(train_set & test_set_idx)

    return {
        "n_total": n,
        "n_train": int(train_idx.size),
        "n_test": int(test_idx.size),
        "overlap_count": len(overlap),
        "overlap_indices_sample": overlap[:10],
        "test_set_mode": test_set,
        "pass": len(overlap) == 0 or test_set == "full_recording",
    }


def run_synthetic_self_test() -> None:
    rng = np.random.default_rng(0)
    labels = np.concatenate(
        [np.full(400, c, dtype=np.int64) for c in range(1, 6)]
    )
    q_all = rng.integers(0, 21, size=(labels.size, 4), dtype=np.int64)

    _, _, test_h1, _ = split_train_test(
        q_all, labels, 0.25, 1, test_set="full_recording"
    )
    assert test_h1.shape[0] == labels.size

    train_idx = compute_train_indices(labels, 0.25, 1)
    test_idx = compute_test_indices(labels, train_idx, boundary_gap=0)
    assert len(set(train_idx.tolist()) & set(test_idx.tolist())) == 0

    _, _, test_h2, _ = split_train_test(
        q_all, labels, 0.25, 1, test_set="disjoint"
    )
    assert test_h2.shape[0] == test_idx.size
    print("  OK  synthetic HDC-2 disjoint split")


def audit_dataset(cfg_path: Path, out_json: Path, out_csv: Path) -> int:
    cfg = load_config(cfg_path)
    require_dataset()
    split_kw = split_kwargs_from_config(cfg)
    seed = int(cfg["seed"])
    train_frac = float(cfg["protocol"]["train_fraction"])
    subjects = cfg["dataset"]["subjects"]
    protocol_id = cfg["protocol"]["id"]

    rows: List[dict] = []
    for subject in subjects:
        mat = sio.loadmat(str(DATASET))
        labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
        _ = quantize_envelope(mat[f"COMPLETE_{subject}"].astype(np.float64))
        row = audit_subject(labels, train_frac, seed, split_kw)
        row["subject"] = subject
        rows.append(row)
        print(
            f"  S{subject}: train={row['n_train']} test={row['n_test']} "
            f"overlap={row['overlap_count']} mode={row['test_set_mode']}"
        )

    total_overlap = sum(r["overlap_count"] for r in rows)
    hdc2_gate = split_kw["test_set"] == "disjoint" and total_overlap == 0

    payload = {
        "config": cfg_path.as_posix(),
        "protocol_id": protocol_id,
        "test_set_mode": split_kw["test_set"],
        "subjects": rows,
        "total_overlap": total_overlap,
        "hdc2_gate_pass": hdc2_gate,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "subject",
                "n_total",
                "n_train",
                "n_test",
                "overlap_count",
                "test_set_mode",
                "pass",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    print(f"\nWrote {out_json}")
    print(f"Wrote {out_csv}")
    print(f"  protocol={protocol_id}  total_overlap={total_overlap}")

    if split_kw["test_set"] == "disjoint":
        if hdc2_gate:
            print("  HDC-2 GATE: PASS (overlap=0)")
            return 0
        print("  HDC-2 GATE: FAIL — fix split before reruns", file=sys.stderr)
        return 1

    print("  HDC-1 mode (full recording test) — informational only")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Audit EMG train/test split leakage")
    p.add_argument(
        "--config",
        type=Path,
        default=PYREF / "config" / "emg_baseline_v2.json",
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=REPO / "results" / "protocol_v2" / "split_audit.json",
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=REPO / "results" / "protocol_v2" / "split_audit.csv",
    )
    p.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Run unit self-test without dataset.mat",
    )
    args = p.parse_args()

    print("== split audit: synthetic self-test ==")
    run_synthetic_self_test()

    if args.synthetic_only:
        return 0

    print(f"\n== split audit: {args.config.name} ==")
    return audit_dataset(args.config, args.out_json, args.out_csv)


if __name__ == "__main__":
    raise SystemExit(main())
