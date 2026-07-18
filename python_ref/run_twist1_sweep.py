#!/usr/bin/env python3
"""
Twist 1 — informed vs random Fisher pruning at identical density.

RTL-matched hdc_ref encoder on the frozen EMG protocol (P-may2026).
Default: D=1024, CNT_W=6, keep_ratio=0.5 (anchor B density).

Per subject: Fisher mask from TRAIN windows vs random mask(s) with the same
number of kept bits. Claim target: informed beats random by ≥5 pp (mean gap).

Usage (from repo root):
  python3 python_ref/run_twist1_sweep.py --quick     # ~5–10 min sanity
  python3 python_ref/run_twist1_sweep.py             # full 5 subjects (hours)

Outputs:
  results/twist1/twist1_results.json
  results/twist1/twist1_summary.csv
  results/twist1/README.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np
import scipy.io as sio

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bundle_majority_unlimited,
    mask_from_scores,
    per_bit_fisher_scores,
)
from export_emg_board_vectors import (  # noqa: E402
    DATASET,
    N_CLASS,
    level21_to_grid,
    quantize_envelope,
    require_dataset,
    split_kwargs_from_config,
    split_train_test,
)

DEFAULT_CFG = HERE / "config" / "twist1_sweep.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline.json"
OUT_DIR = REPO / "results" / "twist1"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hdc_cfg_for_d(D: int, item_mem_seed: int) -> HDCConfig:
    bits_per_word = 64
    return HDCConfig(D=D, words=D // bits_per_word, bits_per_word=bits_per_word, seed=item_mem_seed)


def cap_windows_stratified(
    q: np.ndarray,
    labels: np.ndarray,
    n_max: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Cap windows with per-class slices (HDC-2 test is class-ordered; head-only caps break accuracy)."""
    if q.shape[0] <= n_max:
        return q, labels
    per_class = max(1, n_max // N_CLASS)
    picks: List[int] = []
    for k in range(1, N_CLASS + 1):
        cls_idx = np.where(labels == k)[0]
        if cls_idx.size == 0:
            continue
        picks.extend(cls_idx[: min(per_class, cls_idx.size)].tolist())
    picks = picks[:n_max]
    idx = np.array(picks, dtype=np.int64)
    return q[idx], labels[idx]


def train_prototypes(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    train_q: np.ndarray,
    train_labels: np.ndarray,
    cnt_w: int,
) -> np.ndarray:
    protos = np.zeros((N_CLASS, cfg.D), dtype=np.uint8)
    for k in range(1, N_CLASS + 1):
        idx = np.where(train_labels == k)[0]
        if idx.size == 0:
            continue
        windows = [
            engine.encode_emg_window(level21_to_grid(train_q[i], cfg), mem, cnt_bits=cnt_w)
            for i in idx
        ]
        protos[k - 1] = bundle_majority_unlimited(windows, cfg)
    return protos


def encode_queries(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    q: np.ndarray,
    cnt_w: int,
    progress_label: str = "",
) -> np.ndarray:
    n = q.shape[0]
    out = np.zeros((n, cfg.D), dtype=np.uint8)
    step = max(1, n // 20)
    for i in range(n):
        if progress_label and i > 0 and i % step == 0:
            print(f"      encode {progress_label}: {i}/{n}", flush=True)
        out[i] = engine.encode_emg_window(level21_to_grid(q[i], cfg), mem, cnt_bits=cnt_w)
    return out


def accuracy_with_mask(
    engine: HDCEngine,
    queries: np.ndarray,
    labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> tuple[float, int, int]:
    gt = labels.astype(np.int32) - 1
    correct = 0
    total = int(labels.shape[0])
    for i in range(total):
        pred = engine.classify(queries[i], protos, mask=mask).class_id
        if pred == int(gt[i]):
            correct += 1
    return correct / total if total else 0.0, correct, total


def eval_subject(
    subject: int,
    D: int,
    cnt_w: int,
    keep_ratio: float,
    random_seeds: Sequence[int],
    seed: int,
    train_frac: float,
    item_mem_seed: int,
    max_test_windows: Optional[int],
    max_train_windows: Optional[int],
    split_kw: dict,
) -> dict:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)

    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed, **split_kw
    )
    if max_train_windows is not None and train_q.shape[0] > max_train_windows:
        train_q, train_labels = cap_windows_stratified(train_q, train_labels, max_train_windows)
    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q, test_labels = cap_windows_stratified(test_q, test_labels, max_test_windows)

    cfg = hdc_cfg_for_d(D, item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)

    print(f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}", flush=True)
    train_hvs = encode_queries(engine, mem, cfg, train_q, cnt_w, f"s{subject}/train")
    test_hvs = encode_queries(engine, mem, cfg, test_q, cnt_w, f"s{subject}/test")
    protos = train_prototypes(engine, mem, cfg, train_q, train_labels, cnt_w)

    fisher_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))
    informed_mask = mask_from_scores(fisher_scores, keep_ratio, informed=True)
    n_keep = int(informed_mask.sum())

    unpruned_acc, _, _ = accuracy_with_mask(
        engine, test_hvs, test_labels, protos, np.ones(cfg.D, dtype=np.uint8)
    )
    informed_acc, informed_correct, n_test = accuracy_with_mask(
        engine, test_hvs, test_labels, protos, informed_mask
    )

    random_rows = []
    for rs in random_seeds:
        random_mask = mask_from_scores(
            fisher_scores,
            keep_ratio,
            rng=np.random.default_rng(rs),
            informed=False,
        )
        assert int(random_mask.sum()) == n_keep
        random_acc, random_correct, _ = accuracy_with_mask(
            engine, test_hvs, test_labels, protos, random_mask
        )
        random_rows.append(
            {
                "seed": rs,
                "accuracy": random_acc,
                "correct": random_correct,
                "gap_pp": 100.0 * (informed_acc - random_acc),
            }
        )

    random_accs = [r["accuracy"] for r in random_rows]
    mean_random = float(np.mean(random_accs))
    std_random = float(np.std(random_accs)) if len(random_accs) > 1 else 0.0

    return {
        "subject": subject,
        "D": D,
        "cnt_w": cnt_w,
        "keep_ratio": keep_ratio,
        "n_keep": n_keep,
        "n_train": int(train_q.shape[0]),
        "n_test": n_test,
        "unpruned_accuracy": unpruned_acc,
        "informed_accuracy": informed_acc,
        "informed_correct": informed_correct,
        "random_accuracy_mean": mean_random,
        "random_accuracy_std": std_random,
        "gap_pp_mean": 100.0 * (informed_acc - mean_random),
        "random_by_seed": random_rows,
    }


def write_csv(path: Path, per_subject: List[dict]) -> None:
    fields = [
        "subject",
        "informed_accuracy",
        "random_accuracy_mean",
        "random_accuracy_std",
        "gap_pp_mean",
        "unpruned_accuracy",
        "n_keep",
        "n_test",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in per_subject:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, per_subject: List[dict]) -> None:
    mean_informed = meta["mean_informed_accuracy"]
    mean_random = meta["mean_random_accuracy"]
    mean_gap = meta["mean_gap_pp"]
    target = meta["target_gap_pp"]
    passed = meta["target_met"]

    lines = [
        "# Twist 1 — informed vs random pruning @ iso-density",
        "",
        f"Generated: {meta['generated_at']}",
        f"Config: D={meta['D']}, CNT_W={meta['cnt_w']}, keep={meta['keep_ratio']} "
        f"({meta['n_keep']} bits)",
        f"Random seeds: {meta['random_seeds']}",
        "",
        "## Headline (5-subject mean)",
        "",
        f"| Mask | Spatial mean accuracy |",
        f"|------|----------------------|",
        f"| Unpruned (keep=1.0) | **{100.0 * meta['mean_unpruned_accuracy']:.2f}%** |",
        f"| Fisher informed | **{100.0 * mean_informed:.2f}%** |",
        f"| Random (mean ± std over seeds) | **{100.0 * mean_random:.2f}% ± "
        f"{100.0 * meta['std_random_accuracy']:.2f} pp** |",
        f"| **Gap (informed − random)** | **{mean_gap:+.2f} pp** |",
        "",
        f"Target ≥ {target:.0f} pp: **{'PASS' if passed else 'FAIL (so far)'}**",
        "",
        "## Per subject",
        "",
        "| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |",
        "|---------|----------|---------------|----------|----------|",
    ]
    for row in per_subject:
        lines.append(
            f"| S{row['subject']} | {100.0 * row['informed_accuracy']:.2f}% | "
            f"{100.0 * row['random_accuracy_mean']:.2f}% | "
            f"{row['gap_pp_mean']:+.2f} | {100.0 * row['unpruned_accuracy']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_twist1_sweep.py --quick",
            "python3 python_ref/run_twist1_sweep.py",
            "python3 python_ref/plot_results.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Twist 1 informed vs random pruning sweep")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--subjects", type=int, nargs="*", default=None)
    p.add_argument("--max-windows", type=int, default=None, help="cap TEST windows per subject")
    p.add_argument("--max-train-windows", type=int, default=None)
    p.add_argument("--random-seeds", type=int, nargs="*", default=None)
    p.add_argument("--keep", type=float, default=None, help="override keep_ratio from config")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    twist_cfg = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    D = int(twist_cfg["D"])
    cnt_w = int(twist_cfg["cnt_w"])
    keep_ratio = float(args.keep if args.keep is not None else twist_cfg["keep_ratio"])
    target_gap = float(twist_cfg.get("target_gap_pp", 5.0))
    item_mem_seed = int(twist_cfg["item_mem_seed"])

    if args.quick:
        q = twist_cfg["quick"]
        subjects = args.subjects or q.get("subjects") or twist_cfg["subjects"]
        max_windows = q.get("max_test_windows_per_subject")
        max_train_windows = q.get("max_train_windows_per_subject")
        random_seeds = args.random_seeds or q.get("random_seeds") or twist_cfg["random_seeds"]
    else:
        subjects = args.subjects or twist_cfg["subjects"]
        max_windows = args.max_windows
        max_train_windows = args.max_train_windows
        random_seeds = args.random_seeds or twist_cfg["random_seeds"]

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Twist 1 — informed vs random pruning (hdc_ref / RTL encoder)")
    print(f"  D={D}  CNT_W={cnt_w}  keep={keep_ratio}  seeds={list(random_seeds)}")
    print(f"  subjects: {subjects}")
    print(f"  max_train: {max_train_windows or 'all'}  max_test: {max_windows or 'all'}")
    print("=" * 70)

    t0 = time.time()
    per_subject: List[dict] = []

    for subject in subjects:
        print(f"\n== subject {subject} ==", flush=True)
        row = eval_subject(
            subject,
            D,
            cnt_w,
            keep_ratio,
            random_seeds,
            seed,
            train_frac,
            item_mem_seed,
            max_windows,
            max_train_windows,
            split_kw,
        )
        per_subject.append(row)
        print(
            f"    informed={100.0 * row['informed_accuracy']:.2f}%  "
            f"random={100.0 * row['random_accuracy_mean']:.2f}%  "
            f"gap={row['gap_pp_mean']:+.2f} pp",
            flush=True,
        )
        partial = args.out_dir / "twist1_results.partial.json"
        partial.write_text(
            json.dumps({"status": "running", "per_subject": per_subject}, indent=2),
            encoding="utf-8",
        )

    mean_informed = float(np.mean([r["informed_accuracy"] for r in per_subject]))
    mean_random = float(np.mean([r["random_accuracy_mean"] for r in per_subject]))
    std_random = float(np.mean([r["random_accuracy_std"] for r in per_subject]))
    mean_unpruned = float(np.mean([r["unpruned_accuracy"] for r in per_subject]))
    mean_gap = 100.0 * (mean_informed - mean_random)
    n_keep = per_subject[0]["n_keep"] if per_subject else int(round(D * keep_ratio))

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine": twist_cfg.get("engine", "hdc_ref"),
        "protocol": emg_cfg["protocol"]["id"],
        "subjects": subjects,
        "D": D,
        "cnt_w": cnt_w,
        "keep_ratio": keep_ratio,
        "n_keep": n_keep,
        "random_seeds": list(random_seeds),
        "max_train_windows_per_subject": max_train_windows,
        "max_test_windows_per_subject": max_windows,
        "elapsed_s": round(time.time() - t0, 1),
        "mean_unpruned_accuracy": mean_unpruned,
        "mean_informed_accuracy": mean_informed,
        "mean_random_accuracy": mean_random,
        "std_random_accuracy": std_random,
        "mean_gap_pp": mean_gap,
        "target_gap_pp": target_gap,
        "target_met": mean_gap >= target_gap,
    }

    payload = {"meta": meta, "per_subject": per_subject}
    out_json = args.out_dir / "twist1_results.json"
    out_csv = args.out_dir / "twist1_summary.csv"
    out_readme = args.out_dir / "README.md"

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(out_csv, per_subject)
    write_readme(out_readme, meta, per_subject)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    print(f"  Informed mean: {100.0 * mean_informed:.2f}%")
    print(f"  Random mean:   {100.0 * mean_random:.2f}%")
    print(f"  Gap:           {mean_gap:+.2f} pp  (target ≥ {target_gap:.0f} pp)")
    print(f"  Target met:    {'YES' if meta['target_met'] else 'NO'}")
    print(f"  {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
