#!/usr/bin/env python3
"""
Issue #4 — item-memory seed sensitivity.

Vary item_mem_seed (default {1, 7, 21, 42}) on the HDC-2 EMG protocol. Per seed:
  - Full-width (keep=1.0) spatial-mean accuracy
  - Active bit support (positions that vary across encoded TRAIN+TEST HVs)
  - Fisher vs random gap @ 128 bits (keep=0.125)
  - Retained-bit accuracy curve over keep_ratios

Usage (from repo root):
  python3 python_ref/run_seed_sensitivity.py --quick
  python3 python_ref/run_seed_sensitivity.py --seeds 1,7,21,42

Outputs:
  results/seed_sensitivity/seed_sensitivity_results.json
  results/seed_sensitivity/seed_sensitivity_summary.csv
  results/seed_sensitivity/README.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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

DEFAULT_CFG = HERE / "config" / "seed_sensitivity.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "seed_sensitivity"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hdc_cfg_for_d(D: int, item_mem_seed: int) -> HDCConfig:
    bits_per_word = 64
    return HDCConfig(D=D, words=D // bits_per_word, bits_per_word=bits_per_word, seed=item_mem_seed)


def cap_windows_stratified(
    q: np.ndarray,
    labels: np.ndarray,
    n_max: int,
) -> Tuple[np.ndarray, np.ndarray]:
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


def active_bit_support(hvs: np.ndarray) -> int:
    """Count bit positions that are not constant across hypervectors."""
    if hvs.size == 0:
        return 0
    col_min = np.min(hvs, axis=0)
    col_max = np.max(hvs, axis=0)
    return int(np.sum(col_min != col_max))


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
) -> Tuple[float, int, int]:
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
    item_mem_seed: int,
    keep_ratios: Sequence[float],
    gap_keep_ratio: float,
    random_seeds: Sequence[int],
    seed: int,
    train_frac: float,
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

    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]} "
        f"item_mem_seed={item_mem_seed}",
        flush=True,
    )
    train_hvs = encode_queries(engine, mem, cfg, train_q, cnt_w, f"s{subject}/train")
    test_hvs = encode_queries(engine, mem, cfg, test_q, cnt_w, f"s{subject}/test")
    protos = train_prototypes(engine, mem, cfg, train_q, train_labels, cnt_w)

    pooled_hvs = np.vstack([train_hvs, test_hvs])
    active_support = active_bit_support(pooled_hvs)
    fisher_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))

    keep_curve: List[dict] = []
    for keep in keep_ratios:
        if keep >= 1.0 - 1e-9:
            mask = np.ones(cfg.D, dtype=np.uint8)
        else:
            mask = mask_from_scores(fisher_scores, keep, informed=True)
        acc, correct, n_test = accuracy_with_mask(engine, test_hvs, test_labels, protos, mask)
        keep_curve.append(
            {
                "keep_ratio": keep,
                "n_keep": int(mask.sum()),
                "accuracy": acc,
                "correct": correct,
                "n_test": n_test,
            }
        )

    gap_keep = next(r for r in keep_curve if abs(r["keep_ratio"] - gap_keep_ratio) < 1e-9)
    informed_mask = mask_from_scores(fisher_scores, gap_keep_ratio, informed=True)
    n_keep = int(informed_mask.sum())
    informed_acc = gap_keep["accuracy"]
    informed_correct = gap_keep["correct"]

    random_rows = []
    for rs in random_seeds:
        random_mask = mask_from_scores(
            fisher_scores,
            gap_keep_ratio,
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
    full_width = next(r for r in keep_curve if abs(r["keep_ratio"] - 1.0) < 1e-9)

    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "D": D,
        "cnt_w": cnt_w,
        "active_bit_support": active_support,
        "n_train": int(train_q.shape[0]),
        "n_test": int(test_labels.shape[0]),
        "full_width_accuracy": full_width["accuracy"],
        "keep_curve": keep_curve,
        "gap_keep_ratio": gap_keep_ratio,
        "n_keep_at_gap": n_keep,
        "informed_accuracy_at_gap": informed_acc,
        "informed_correct_at_gap": informed_correct,
        "random_accuracy_mean_at_gap": mean_random,
        "random_accuracy_std_at_gap": std_random,
        "gap_pp_mean_at_gap": 100.0 * (informed_acc - mean_random),
        "random_by_seed_at_gap": random_rows,
    }


def aggregate_by_item_seed(per_subject: List[dict]) -> List[dict]:
    buckets: Dict[int, List[dict]] = {}
    for row in per_subject:
        buckets.setdefault(row["item_mem_seed"], []).append(row)

    summary = []
    for item_seed, group in sorted(buckets.items()):
        full_accs = [g["full_width_accuracy"] for g in group]
        active = [g["active_bit_support"] for g in group]
        informed = [g["informed_accuracy_at_gap"] for g in group]
        random_m = [g["random_accuracy_mean_at_gap"] for g in group]
        gaps = [g["gap_pp_mean_at_gap"] for g in group]

        keep_keys = sorted({kr["keep_ratio"] for g in group for kr in g["keep_curve"]})
        keep_means = {}
        for keep in keep_keys:
            accs = []
            for g in group:
                for kr in g["keep_curve"]:
                    if abs(kr["keep_ratio"] - keep) < 1e-9:
                        accs.append(kr["accuracy"])
                        break
            keep_means[str(keep)] = float(np.mean(accs)) if accs else None

        summary.append(
            {
                "item_mem_seed": item_seed,
                "spatial_mean_full_width_accuracy": float(np.mean(full_accs)),
                "spatial_mean_active_bit_support": float(np.mean(active)),
                "spatial_mean_informed_accuracy_at_gap": float(np.mean(informed)),
                "spatial_mean_random_accuracy_at_gap": float(np.mean(random_m)),
                "spatial_mean_gap_pp_at_gap": float(np.mean(gaps)),
                "per_subject_full_width_accuracy": {
                    str(g["subject"]): g["full_width_accuracy"] for g in group
                },
                "keep_curve_spatial_mean": keep_means,
            }
        )
    return summary


def write_csv(path: Path, summary: List[dict]) -> None:
    fields = [
        "item_mem_seed",
        "spatial_mean_full_width_accuracy",
        "spatial_mean_active_bit_support",
        "spatial_mean_informed_accuracy_at_gap",
        "spatial_mean_random_accuracy_at_gap",
        "spatial_mean_gap_pp_at_gap",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in summary:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, summary: List[dict]) -> None:
    lines = [
        "# Issue 4 — item-memory seed sensitivity",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · Engine: **{meta['engine']}**",
        f"D={meta['D']}  CNT_W={meta['cnt_w']}  gap keep={meta['gap_keep_ratio']} "
        f"({meta['n_keep_at_gap']} bits)",
        "",
        "## Spatial mean (5 subjects)",
        "",
        "| item_mem_seed | Full-width acc | Active support | Fisher @128 | Random @128 | Gap (pp) |",
        "|---------------|----------------|----------------|-------------|-------------|----------|",
    ]
    for row in summary:
        lines.append(
            f"| {row['item_mem_seed']} | {100.0 * row['spatial_mean_full_width_accuracy']:.2f}% | "
            f"{row['spatial_mean_active_bit_support']:.0f} | "
            f"{100.0 * row['spatial_mean_informed_accuracy_at_gap']:.2f}% | "
            f"{100.0 * row['spatial_mean_random_accuracy_at_gap']:.2f}% | "
            f"{row['spatial_mean_gap_pp_at_gap']:+.2f} |"
        )

    lines.extend(
        [
            "",
            "## Keep-ratio curve (spatial mean accuracy)",
            "",
        ]
    )
    if summary:
        keeps = sorted(float(k) for k in summary[0]["keep_curve_spatial_mean"])
        header = "| item_mem_seed | " + " | ".join(f"keep={k:g}" for k in keeps) + " |"
        sep = "|---|" + "|".join("---" for _ in keeps) + "|"
        lines.extend([header, sep])
        for row in summary:
            cells = [
                f"{100.0 * row['keep_curve_spatial_mean'][str(k)]:.2f}%"
                for k in keeps
            ]
            lines.append(f"| {row['item_mem_seed']} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_seed_sensitivity.py --quick",
            "python3 python_ref/run_seed_sensitivity.py --seeds 1,7,21,42",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checkpoint(out_dir: Path, meta: dict, per_subject: List[dict]) -> None:
    path = out_dir / "seed_sensitivity_results.partial.json"
    path.write_text(
        json.dumps({"meta": meta, "per_subject": per_subject}, indent=2),
        encoding="utf-8",
    )


def parse_seeds(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 4 item-memory seed sensitivity")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--seeds", type=str, default=None, help="item_mem seeds, e.g. 1,7,21,42")
    p.add_argument("--subjects", type=int, nargs="*", default=None)
    p.add_argument("--max-windows", type=int, default=None)
    p.add_argument("--max-train-windows", type=int, default=None)
    p.add_argument("--random-seeds", type=int, nargs="*", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    sweep_cfg = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    D = int(sweep_cfg["D"])
    cnt_w = int(sweep_cfg["cnt_w"])
    keep_ratios = [float(k) for k in sweep_cfg["keep_ratios"]]
    gap_keep_ratio = float(sweep_cfg["gap_keep_ratio"])
    n_keep_at_gap = int(round(D * gap_keep_ratio))

    if args.quick:
        q = sweep_cfg["quick"]
        item_mem_seeds = (
            parse_seeds(args.seeds) if args.seeds else q.get("item_mem_seeds") or sweep_cfg["item_mem_seeds"]
        )
        subjects = args.subjects or q.get("subjects") or sweep_cfg["subjects"]
        max_windows = q.get("max_test_windows_per_subject")
        max_train_windows = q.get("max_train_windows_per_subject")
        random_seeds = args.random_seeds or q.get("random_seeds") or sweep_cfg["random_seeds"]
    else:
        item_mem_seeds = parse_seeds(args.seeds) if args.seeds else sweep_cfg["item_mem_seeds"]
        subjects = args.subjects or sweep_cfg["subjects"]
        max_windows = args.max_windows
        max_train_windows = args.max_train_windows
        random_seeds = args.random_seeds or sweep_cfg["random_seeds"]

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Issue 4 — item-memory seed sensitivity (hdc_ref / RTL encoder)")
    print(f"  protocol={protocol_id}  D={D}  CNT_W={cnt_w}")
    print(f"  item_mem_seeds={list(item_mem_seeds)}  keep_ratios={keep_ratios}")
    print(f"  gap @ keep={gap_keep_ratio}  random_seeds={list(random_seeds)}")
    print(f"  subjects={subjects}")
    print(f"  max_train={max_train_windows or 'all'}  max_test={max_windows or 'all'}")
    print("=" * 70)

    t0 = time.time()
    per_subject: List[dict] = []
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 4,
        "engine": sweep_cfg.get("engine", "hdc_ref"),
        "protocol": protocol_id,
        "emg_config": str(args.emg_config.relative_to(REPO)),
        "subjects": subjects,
        "D": D,
        "cnt_w": cnt_w,
        "item_mem_seeds": list(item_mem_seeds),
        "keep_ratios": keep_ratios,
        "gap_keep_ratio": gap_keep_ratio,
        "n_keep_at_gap": n_keep_at_gap,
        "random_seeds": list(random_seeds),
        "max_train_windows_per_subject": max_train_windows,
        "max_test_windows_per_subject": max_windows,
    }

    for item_mem_seed in item_mem_seeds:
        print(f"\n== item_mem_seed={item_mem_seed} ==", flush=True)
        for subject in subjects:
            print(f"\n== subject {subject} ==", flush=True)
            row = eval_subject(
                subject,
                D,
                cnt_w,
                item_mem_seed,
                keep_ratios,
                gap_keep_ratio,
                random_seeds,
                seed,
                train_frac,
                max_windows,
                max_train_windows,
                split_kw,
            )
            per_subject.append(row)
            meta["elapsed_s"] = round(time.time() - t0, 1)
            _write_checkpoint(args.out_dir, meta, per_subject)

    summary = aggregate_by_item_seed(per_subject)
    meta["elapsed_s"] = round(time.time() - t0, 1)
    meta["summary"] = summary

    if len(item_mem_seeds) > 1:
        ref_seed = 42 if 42 in item_mem_seeds else item_mem_seeds[0]
        ref_row = next(s for s in summary if s["item_mem_seed"] == ref_seed)
        meta["reference_item_mem_seed"] = ref_seed
        meta["full_width_spread_pp"] = round(
            100.0
            * (
                max(s["spatial_mean_full_width_accuracy"] for s in summary)
                - min(s["spatial_mean_full_width_accuracy"] for s in summary)
            ),
            3,
        )
        meta["gap_spread_pp"] = round(
            max(s["spatial_mean_gap_pp_at_gap"] for s in summary)
            - min(s["spatial_mean_gap_pp_at_gap"] for s in summary),
            3,
        )

    out_json = args.out_dir / "seed_sensitivity_results.json"
    out_json.write_text(json.dumps({"meta": meta, "per_subject": per_subject}, indent=2), encoding="utf-8")
    write_csv(args.out_dir / "seed_sensitivity_summary.csv", summary)
    write_readme(args.out_dir / "README.md", meta, summary)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    for row in summary:
        print(
            f"  seed={row['item_mem_seed']:>2}: full={100.0 * row['spatial_mean_full_width_accuracy']:.2f}% "
            f"active={row['spatial_mean_active_bit_support']:.0f} "
            f"gap@128={row['spatial_mean_gap_pp_at_gap']:+.2f} pp"
        )
    print(f"Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
