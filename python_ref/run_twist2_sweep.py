#!/usr/bin/env python3
"""
Twist 2 — cross-subject Fisher mask transfer (5-subject pilot).

Train an informed Fisher mask on TRAIN windows from a subject subset; evaluate on
held-out subjects' TEST windows. Each test subject uses its own prototypes (TRAIN
bundles) — only the mask is transferred.

Compare on held-out TEST split:
  - **local_oracle** — per-subject Fisher mask from own TRAIN (upper bound)
  - **pooled_transfer** — one mask from pooled Fisher on train-subject TRAIN data
  - **unpruned** — all-ones mask (reference)

Claim target: |local − pooled| ≤ 3 pp → mask generalises; larger gap → per-subject
calibration needed (either outcome is publishable).

Usage (from repo root):
  python3 python_ref/run_twist2_sweep.py --quick     # pipeline sanity
  python3 python_ref/run_twist2_sweep.py            # full pilot (~hours)

Outputs:
  results/twist2/twist2_results.json
  results/twist2/twist2_summary.csv
  results/twist2/README.md
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

DEFAULT_CFG = HERE / "config" / "twist2_sweep.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline.json"
OUT_DIR = REPO / "results" / "twist2"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hdc_cfg_for_d(D: int, item_mem_seed: int) -> HDCConfig:
    return HDCConfig(D=D, words=D // 64, bits_per_word=64, seed=item_mem_seed)


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
    progress_label: str = "",
) -> tuple[float, int, int]:
    gt = labels.astype(np.int32) - 1
    correct = 0
    total = int(labels.shape[0])
    step = max(1, total // 20)
    for i in range(total):
        if progress_label and i > 0 and i % step == 0:
            print(f"      classify {progress_label}: {i}/{total}", flush=True)
        pred = engine.classify(queries[i], protos, mask=mask).class_id
        if pred == int(gt[i]):
            correct += 1
    return correct / total if total else 0.0, correct, total


def encode_cache_dir(out_dir: Path) -> Path:
    return out_dir / "encode_cache"


def manifest_path(out_dir: Path) -> Path:
    return encode_cache_dir(out_dir) / "manifest.json"


def subject_cache_path(out_dir: Path, subject: int) -> Path:
    return encode_cache_dir(out_dir) / f"s{subject:02d}.npz"


def build_manifest(
    *,
    D: int,
    cnt_w: int,
    item_mem_seed: int,
    seed: int,
    train_frac: float,
    dataset_path: Path,
    protocol_id: str,
    split_kw: dict,
    train_subjects: Sequence[int],
    test_subjects: Sequence[int],
    max_train: Optional[int],
    max_test: Optional[int],
    subjects_done: Sequence[int],
) -> dict:
    return {
        "D": D,
        "cnt_w": cnt_w,
        "item_mem_seed": item_mem_seed,
        "seed": seed,
        "train_frac": train_frac,
        "dataset": str(dataset_path),
        "protocol_id": protocol_id,
        "split_kw": split_kw,
        "train_subjects": list(train_subjects),
        "test_subjects": list(test_subjects),
        "max_train_windows_per_subject": max_train,
        "max_test_windows_per_subject": max_test,
        "subjects_done": sorted(subjects_done),
    }


def validate_manifest(out_dir: Path, expected: dict) -> dict:
    path = manifest_path(out_dir)
    if not path.is_file():
        raise FileNotFoundError(f"missing encode cache manifest: {path}")
    manifest = load_json(path)
    keys = (
        "D",
        "cnt_w",
        "item_mem_seed",
        "seed",
        "train_frac",
        "dataset",
        "protocol_id",
        "split_kw",
        "train_subjects",
        "test_subjects",
        "max_train_windows_per_subject",
        "max_test_windows_per_subject",
    )
    for key in keys:
        if manifest.get(key) != expected[key]:
            raise ValueError(
                f"encode cache mismatch on {key!r}: cache={manifest.get(key)!r} "
                f"expected={expected[key]!r}"
            )
    return manifest


def save_subject_cache(
    out_dir: Path,
    subject: int,
    *,
    train_hvs: Optional[np.ndarray],
    train_labels: Optional[np.ndarray],
    test_hvs: Optional[np.ndarray],
    test_labels: Optional[np.ndarray],
    protos: Optional[np.ndarray],
    local_scores: np.ndarray,
    n_train: int,
    n_test: int,
) -> None:
    cache_dir = encode_cache_dir(out_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "local_scores": local_scores.astype(np.float64),
        "n_train": np.int64(n_train),
        "n_test": np.int64(n_test),
    }
    if train_hvs is not None:
        payload["train_hvs"] = train_hvs
        payload["train_labels"] = train_labels.astype(np.int32)
    if test_hvs is not None:
        payload["test_hvs"] = test_hvs
        payload["test_labels"] = test_labels.astype(np.int32)
    if protos is not None:
        payload["protos"] = protos
    np.savez_compressed(subject_cache_path(out_dir, subject), **payload)


def load_subject_cache(out_dir: Path, subject: int) -> dict:
    path = subject_cache_path(out_dir, subject)
    if not path.is_file():
        raise FileNotFoundError(f"missing subject cache: {path}")
    with np.load(path, allow_pickle=False) as z:
        out = {
            "local_scores": z["local_scores"],
            "n_train": int(z["n_train"]),
            "n_test": int(z["n_test"]),
        }
        for key in ("train_hvs", "train_labels", "test_hvs", "test_labels", "protos"):
            if key in z:
                out[key] = z[key]
    return out


def _empty_fisher_stats(D: int) -> dict:
    return {
        "classes": {},
        "total_n": 0,
    }


def _accumulate_fisher_chunk(stats: dict, hvs: np.ndarray, labels: np.ndarray) -> None:
    x = np.asarray(hvs, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int32)
    D = x.shape[1]
    stats["total_n"] += int(x.shape[0])
    for c in np.unique(y):
        idx = y == c
        xc = x[idx]
        cls = stats["classes"].setdefault(
            int(c),
            {"n": 0, "sum": np.zeros(D, dtype=np.float64), "sum_sq": np.zeros(D, dtype=np.float64)},
        )
        cls["n"] += int(idx.sum())
        cls["sum"] += xc.sum(axis=0)
        cls["sum_sq"] += (xc * xc).sum(axis=0)


def _fisher_scores_from_stats(stats: dict, D: int) -> np.ndarray:
    scores = np.zeros(D, dtype=np.float64)
    eps = 1e-6
    total_n = stats["total_n"]
    if total_n <= 1:
        return scores
    total_sum = np.zeros(D, dtype=np.float64)
    total_sum_sq = np.zeros(D, dtype=np.float64)
    for cls in stats["classes"].values():
        total_sum += cls["sum"]
        total_sum_sq += cls["sum_sq"]
    overall_mean = total_sum / total_n
    overall_var = total_sum_sq / total_n - overall_mean * overall_mean
    for bit in range(D):
        if overall_var[bit] < eps:
            scores[bit] = 0.0
            continue
        within = 0.0
        for cls in stats["classes"].values():
            n_c = cls["n"]
            if n_c <= 1:
                continue
            mean_c = cls["sum"][bit] / n_c
            var_c = cls["sum_sq"][bit] / n_c - mean_c * mean_c
            within += var_c * n_c
        within /= max(1, total_n)
        scores[bit] = overall_var[bit] / (within + eps)
    return scores


def pooled_fisher_scores_from_cache(
    out_dir: Path, train_subjects: Sequence[int], D: int
) -> np.ndarray:
    stats = _empty_fisher_stats(D)
    for sid in train_subjects:
        cached = load_subject_cache(out_dir, sid)
        if "train_hvs" not in cached:
            raise KeyError(f"S{sid} cache missing train_hvs required for pooled Fisher mask")
        _accumulate_fisher_chunk(stats, cached["train_hvs"], cached["train_labels"])
        print(f"    pooled Fisher: absorbed S{sid} train ({cached['train_hvs'].shape[0]} windows)", flush=True)
    return _fisher_scores_from_stats(stats, D)


def _write_eval_checkpoint(out_dir: Path, meta: dict, per_test: List[dict]) -> None:
    path = out_dir / "twist2_results.partial.json"
    path.write_text(
        json.dumps({"meta": meta, "per_test_subject": per_test}, indent=2),
        encoding="utf-8",
    )


def load_subject_data(
    subject: int,
    seed: int,
    train_frac: float,
    max_train: Optional[int],
    max_test: Optional[int],
    dataset_path: Path,
    split_kw: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mat = sio.loadmat(str(dataset_path))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)
    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed, **split_kw
    )
    if max_train is not None and train_q.shape[0] > max_train:
        train_q = train_q[:max_train]
        train_labels = train_labels[:max_train]
    if max_test is not None and test_q.shape[0] > max_test:
        test_q = test_q[:max_test]
        test_labels = test_labels[:max_test]
    return train_q, train_labels, test_q, test_labels


def encode_subjects(
    train_subjects: Sequence[int],
    test_subjects: Sequence[int],
    D: int,
    cnt_w: int,
    seed: int,
    train_frac: float,
    item_mem_seed: int,
    max_train: Optional[int],
    max_test: Optional[int],
    dataset_path: Path,
    split_kw: dict,
    out_dir: Path,
    protocol_id: str,
    *,
    resume: bool,
) -> None:
    cfg = hdc_cfg_for_d(D, item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    all_subjects = sorted(set(train_subjects) | set(test_subjects))
    subjects_done: List[int] = []

    for sid in all_subjects:
        cache_path = subject_cache_path(out_dir, sid)
        if resume and cache_path.is_file():
            print(f"\n== encode subject {sid} == (cached, skip)", flush=True)
            subjects_done.append(sid)
            continue

        need_test = sid in test_subjects
        print(f"\n== encode subject {sid} ==", flush=True)
        train_q, train_labels, test_q, test_labels = load_subject_data(
            sid, seed, train_frac, max_train, max_test, dataset_path, split_kw
        )
        n_test = int(test_q.shape[0]) if need_test else 0
        print(f"    train={train_q.shape[0]} test={n_test if need_test else 'skip'}", flush=True)

        train_hvs = encode_queries(engine, mem, cfg, train_q, cnt_w, f"s{sid}/train")
        test_hvs = None
        test_labels_out = None
        protos = None
        if need_test:
            test_hvs = encode_queries(engine, mem, cfg, test_q, cnt_w, f"s{sid}/test")
            test_labels_out = test_labels
            protos = train_prototypes(engine, mem, cfg, train_q, train_labels, cnt_w)

        local_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))
        save_subject_cache(
            out_dir,
            sid,
            train_hvs=train_hvs,
            train_labels=train_labels,
            test_hvs=test_hvs,
            test_labels=test_labels_out,
            protos=protos,
            local_scores=local_scores,
            n_train=int(train_q.shape[0]),
            n_test=n_test,
        )
        subjects_done.append(sid)
        print(f"    cached -> {cache_path.name}", flush=True)

    manifest = build_manifest(
        D=D,
        cnt_w=cnt_w,
        item_mem_seed=item_mem_seed,
        seed=seed,
        train_frac=train_frac,
        dataset_path=dataset_path,
        protocol_id=protocol_id,
        split_kw=split_kw,
        train_subjects=train_subjects,
        test_subjects=test_subjects,
        max_train=max_train,
        max_test=max_test,
        subjects_done=subjects_done,
    )
    manifest_path(out_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def evaluate_from_cache(
    train_subjects: Sequence[int],
    test_subjects: Sequence[int],
    D: int,
    cnt_w: int,
    keep_ratio: float,
    item_mem_seed: int,
    out_dir: Path,
    *,
    eval_meta: Optional[dict] = None,
) -> dict:
    cfg = hdc_cfg_for_d(D, item_mem_seed)
    engine = HDCEngine(cfg)

    print("\n== pooled Fisher mask (train subjects) ==", flush=True)
    pooled_scores = pooled_fisher_scores_from_cache(out_dir, train_subjects, D)
    if keep_ratio >= 1.0 - 1e-9:
        pooled_mask = np.ones(cfg.D, dtype=np.uint8)
    else:
        pooled_mask = mask_from_scores(pooled_scores, keep_ratio, informed=True)
    full_mask = np.ones(cfg.D, dtype=np.uint8)
    n_keep = int(pooled_mask.sum())
    print(f"    keep={keep_ratio} -> {n_keep} active bits", flush=True)

    per_test: List[dict] = []
    for sid in test_subjects:
        cached = load_subject_cache(out_dir, sid)
        if "test_hvs" not in cached or "protos" not in cached:
            raise KeyError(f"S{sid} cache missing test/protos required for evaluation")
        local_mask = mask_from_scores(cached["local_scores"], keep_ratio, informed=True)
        label = f"S{sid}/test"
        unpruned_acc, _, _ = accuracy_with_mask(
            engine, cached["test_hvs"], cached["test_labels"], cached["protos"], full_mask, label
        )
        local_acc, _, _ = accuracy_with_mask(
            engine, cached["test_hvs"], cached["test_labels"], cached["protos"], local_mask, label
        )
        pooled_acc, _, _ = accuracy_with_mask(
            engine, cached["test_hvs"], cached["test_labels"], cached["protos"], pooled_mask, label
        )
        row = {
            "subject": sid,
            "n_test": cached["n_test"],
            "unpruned_accuracy": unpruned_acc,
            "local_oracle_accuracy": local_acc,
            "pooled_transfer_accuracy": pooled_acc,
            "gap_local_minus_pooled_pp": 100.0 * (local_acc - pooled_acc),
        }
        per_test.append(row)
        print(
            f"    test S{sid}: local={100*local_acc:.2f}%  pooled={100*pooled_acc:.2f}%  "
            f"Δ={100*(local_acc-pooled_acc):+.2f} pp",
            flush=True,
        )
        if eval_meta is not None:
            _write_eval_checkpoint(out_dir, eval_meta, per_test)

    pooled_train_windows = sum(
        load_subject_cache(out_dir, sid)["train_hvs"].shape[0] for sid in train_subjects
    )
    mean_local = float(np.mean([r["local_oracle_accuracy"] for r in per_test]))
    mean_pooled = float(np.mean([r["pooled_transfer_accuracy"] for r in per_test]))
    mean_unpruned = float(np.mean([r["unpruned_accuracy"] for r in per_test]))
    mean_gap = 100.0 * (mean_local - mean_pooled)

    return {
        "train_subjects": list(train_subjects),
        "test_subjects": list(test_subjects),
        "D": D,
        "cnt_w": cnt_w,
        "keep_ratio": keep_ratio,
        "n_keep": n_keep,
        "pooled_train_windows": int(pooled_train_windows),
        "per_test_subject": per_test,
        "mean_unpruned_accuracy": mean_unpruned,
        "mean_local_oracle_accuracy": mean_local,
        "mean_pooled_transfer_accuracy": mean_pooled,
        "mean_gap_local_minus_pooled_pp": mean_gap,
    }


def run_experiment(
    train_subjects: Sequence[int],
    test_subjects: Sequence[int],
    D: int,
    cnt_w: int,
    keep_ratio: float,
    seed: int,
    train_frac: float,
    item_mem_seed: int,
    max_train: Optional[int],
    max_test: Optional[int],
    dataset_path: Path,
    split_kw: dict,
    out_dir: Path,
    *,
    resume: bool = False,
    evaluate_only: bool = False,
    protocol_id: str = "",
    eval_meta: Optional[dict] = None,
) -> dict:
    manifest_expected = {
        "D": D,
        "cnt_w": cnt_w,
        "item_mem_seed": item_mem_seed,
        "seed": seed,
        "train_frac": train_frac,
        "dataset": str(dataset_path),
        "protocol_id": protocol_id,
        "split_kw": split_kw,
        "train_subjects": list(train_subjects),
        "test_subjects": list(test_subjects),
        "max_train_windows_per_subject": max_train,
        "max_test_windows_per_subject": max_test,
    }

    all_subjects = sorted(set(train_subjects) | set(test_subjects))
    if evaluate_only:
        manifest = validate_manifest(out_dir, manifest_expected)
        missing = [sid for sid in all_subjects if not subject_cache_path(out_dir, sid).is_file()]
        if missing:
            raise FileNotFoundError(
                f"--evaluate-only requires encode cache for all subjects; missing S{missing}"
            )
        print(f"Loaded encode cache for {len(all_subjects)} subjects", flush=True)
    else:
        encode_subjects(
            train_subjects,
            test_subjects,
            D,
            cnt_w,
            seed,
            train_frac,
            item_mem_seed,
            max_train,
            max_test,
            dataset_path,
            split_kw,
            out_dir,
            protocol_id,
            resume=resume,
        )

    result = evaluate_from_cache(
        train_subjects,
        test_subjects,
        D,
        cnt_w,
        keep_ratio,
        item_mem_seed,
        out_dir,
        eval_meta=eval_meta,
    )
    return result


def write_csv(path: Path, rows: List[dict]) -> None:
    fields = [
        "subject",
        "local_oracle_accuracy",
        "pooled_transfer_accuracy",
        "gap_local_minus_pooled_pp",
        "unpruned_accuracy",
        "n_test",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, result: dict) -> None:
    gap = result["mean_gap_local_minus_pooled_pp"]
    target = meta["target_gap_pp"]
    generalises = abs(gap) <= target
    lines = [
        "# Twist 2 — cross-subject Fisher mask transfer",
        "",
        f"Generated: {meta['generated_at']}",
        f"Train subjects: {result['train_subjects']}  ·  Test subjects: {result['test_subjects']}",
        f"Config: D={result['D']}, CNT_W={result['cnt_w']}, keep={result['keep_ratio']} "
        f"({result['n_keep']} bits)",
        f"Pooled TRAIN windows (mask source): {result['pooled_train_windows']}",
        "",
        "## Headline (held-out test subjects, mean)",
        "",
        f"| Condition | Spatial mean accuracy |",
        f"|-----------|----------------------|",
        f"| Unpruned | **{100.0 * result['mean_unpruned_accuracy']:.2f}%** |",
        f"| Local oracle (own-subject mask) | **{100.0 * result['mean_local_oracle_accuracy']:.2f}%** |",
        f"| Pooled transfer (train-subject mask) | **{100.0 * result['mean_pooled_transfer_accuracy']:.2f}%** |",
        f"| **Gap (local − pooled)** | **{gap:+.2f} pp** |",
        "",
        f"Target |gap| ≤ {target:.0f} pp: **{'GENERALISES' if generalises else 'PER-SUBJECT CALIBRATION LIKELY'}**",
        "",
        "## Per held-out subject",
        "",
        "| Subject | Local oracle | Pooled transfer | Gap (pp) | Unpruned |",
        "|---------|--------------|-----------------|----------|----------|",
    ]
    for row in result["per_test_subject"]:
        lines.append(
            f"| S{row['subject']} | {100.0 * row['local_oracle_accuracy']:.2f}% | "
            f"{100.0 * row['pooled_transfer_accuracy']:.2f}% | "
            f"{row['gap_local_minus_pooled_pp']:+.2f} | "
            f"{100.0 * row['unpruned_accuracy']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_twist2_sweep.py --quick",
            "python3 python_ref/run_twist2_sweep.py",
            "python3 python_ref/plot_results.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_dataset_path(twist_cfg: dict, override: Optional[Path]) -> Path:
    if override is not None:
        return override.resolve()
    rel = twist_cfg.get("dataset_mat")
    if rel:
        return (HERE / rel).resolve()
    return DATASET.resolve()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Twist 2 cross-subject mask transfer")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--dataset", type=Path, default=None, help="Override dataset.mat path")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--keep", type=float, default=None)
    p.add_argument("--max-train-windows", type=int, default=None)
    p.add_argument("--max-test-windows", type=int, default=None)
    p.add_argument(
        "--resume",
        action="store_true",
        help="Skip encoding for subjects with a cached encode_cache/sXX.npz file",
    )
    p.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Run pooled Fisher + held-out evaluation from encode_cache/ only",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    twist_cfg = load_json(args.config)
    dataset_path = resolve_dataset_path(twist_cfg, args.dataset)
    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"dataset not found: {dataset_path}\n"
            "Build 36-subject mat: python3 scripts/build_uci_emg_dataset.py"
        )

    emg_cfg = load_json(args.emg_config)

    D = int(twist_cfg["D"])
    cnt_w = int(twist_cfg["cnt_w"])
    keep_ratio = float(args.keep if args.keep is not None else twist_cfg["keep_ratio"])
    target_gap = float(twist_cfg.get("target_gap_pp", 3.0))
    item_mem_seed = int(twist_cfg["item_mem_seed"])

    if args.quick:
        q = twist_cfg["quick"]
        train_subjects = q["train_subjects"]
        test_subjects = q["test_subjects"]
        max_train = q.get("max_train_windows_per_subject")
        max_test = q.get("max_test_windows_per_subject")
    else:
        train_subjects = twist_cfg["train_subjects"]
        test_subjects = twist_cfg["test_subjects"]
        max_train = args.max_train_windows
        max_test = args.max_test_windows

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = str(emg_cfg["protocol"]["id"])

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Twist 2 — cross-subject mask transfer")
    print(f"  train={train_subjects}  test={test_subjects}")
    print(f"  D={D}  CNT_W={cnt_w}  keep={keep_ratio}")
    print(f"  dataset={dataset_path}")
    print(f"  max_train={max_train or 'all'}  max_test={max_test or 'all'}")
    if args.resume:
        print("  mode=resume (skip cached subjects)")
    if args.evaluate_only:
        print("  mode=evaluate-only")
    print("=" * 70)

    t0 = time.time()
    eval_meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine": twist_cfg.get("engine", "hdc_ref"),
        "protocol": protocol_id,
        "keep_ratio": keep_ratio,
    }
    result = run_experiment(
        train_subjects,
        test_subjects,
        D,
        cnt_w,
        keep_ratio,
        seed,
        train_frac,
        item_mem_seed,
        max_train,
        max_test,
        dataset_path,
        split_kw,
        args.out_dir,
        resume=args.resume,
        evaluate_only=args.evaluate_only,
        protocol_id=protocol_id,
        eval_meta=eval_meta,
    )

    gap = result["mean_gap_local_minus_pooled_pp"]
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine": twist_cfg.get("engine", "hdc_ref"),
        "dataset": str(dataset_path),
        "protocol": emg_cfg["protocol"]["id"],
        "target_gap_pp": target_gap,
        "generalises": abs(gap) <= target_gap,
        "elapsed_s": round(time.time() - t0, 1),
        "max_train_windows_per_subject": max_train,
        "max_test_windows_per_subject": max_test,
    }

    payload = {"meta": meta, "result": result}
    out_json = args.out_dir / "twist2_results.json"
    out_csv = args.out_dir / "twist2_summary.csv"
    out_readme = args.out_dir / "README.md"

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(out_csv, result["per_test_subject"])
    write_readme(out_readme, meta, result)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    print(f"  Local oracle (test mean):  {100.0 * result['mean_local_oracle_accuracy']:.2f}%")
    print(f"  Pooled transfer:         {100.0 * result['mean_pooled_transfer_accuracy']:.2f}%")
    print(f"  Gap (local − pooled):    {gap:+.2f} pp  (target |gap| ≤ {target_gap:.0f} pp)")
    print(f"  Generalises:             {'YES' if meta['generalises'] else 'NO'}")
    print(f"  {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
