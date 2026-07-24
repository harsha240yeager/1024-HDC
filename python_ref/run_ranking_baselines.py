#!/usr/bin/env python3
"""
Issue #9 — ranking baselines beyond Fisher at keep=128 bits.

Encode each subject once under HDC-2, then compare bit-ranking methods that
select the top-K positions (K = keep_ratio * D). Random methods average over
several seeds; informed methods are deterministic.

Usage (from repo root):
  python3 python_ref/run_ranking_baselines.py --quick
  python3 python_ref/run_ranking_baselines.py

Outputs:
  results/protocol_v2/ranking_baselines/ranking_baselines_results.json
  results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv
  results/protocol_v2/ranking_baselines/README.md
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
    active_bit_mask,
    active_bit_support,
    bundle_majority_unlimited,
    mask_from_scores,
    mask_random_from_support,
    mask_topk_from_scores,
    per_bit_class_mean_separation_scores,
    per_bit_entropy_scores,
    per_bit_fisher_scores,
    per_bit_mutual_information_scores,
    per_bit_prototype_disagreement_scores,
    per_bit_variance_scores,
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

DEFAULT_CFG = HERE / "config" / "ranking_baselines.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "ranking_baselines"

# Method metadata for the paper table
METHOD_META: Dict[str, dict] = {
    "fisher": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": True,
        "kind": "informed",
    },
    "variance": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": False,
        "kind": "informed",
    },
    "mutual_information": {
        "ranking_cost": "medium",
        "requires_retraining": False,
        "labels": True,
        "kind": "informed",
    },
    "class_mean_separation": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": True,
        "kind": "informed",
    },
    "prototype_disagreement": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": False,
        "kind": "informed",
    },
    "entropy": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": False,
        "kind": "informed",
    },
    "random_full": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": False,
        "kind": "random",
    },
    "random_active": {
        "ranking_cost": "low",
        "requires_retraining": False,
        "labels": False,
        "kind": "random",
    },
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hdc_cfg_for_d(D: int, item_mem_seed: int) -> HDCConfig:
    bits_per_word = 64
    return HDCConfig(D=D, words=D // bits_per_word, bits_per_word=bits_per_word, seed=item_mem_seed)


def cap_windows_random(
    q: np.ndarray,
    labels: np.ndarray,
    n_max: int,
    *,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    if q.shape[0] <= n_max:
        return q, labels
    if rng is None:
        rng = np.random.default_rng(0)
    idx = rng.choice(q.shape[0], size=int(n_max), replace=False)
    idx.sort()
    return q[idx], labels[idx]


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


def train_prototypes_from_hvs(
    train_hvs: np.ndarray,
    train_labels: np.ndarray,
    cfg: HDCConfig,
) -> np.ndarray:
    protos = np.zeros((N_CLASS, cfg.D), dtype=np.uint8)
    for k in range(1, N_CLASS + 1):
        idx = np.where(train_labels == k)[0]
        if idx.size == 0:
            continue
        protos[k - 1] = bundle_majority_unlimited([train_hvs[i] for i in idx], cfg)
    return protos


def accuracy_with_mask(
    queries: np.ndarray,
    labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> Tuple[float, int, int]:
    total = int(labels.shape[0])
    if total == 0:
        return 0.0, 0, 0
    m = (np.asarray(mask, dtype=np.uint8) & 1).reshape(1, -1)
    q = np.asarray(queries, dtype=np.uint8)
    p = np.asarray(protos, dtype=np.uint8)
    dists = np.stack([((q ^ p[k]) & m).sum(axis=1) for k in range(p.shape[0])], axis=1)
    pred = dists.argmin(axis=1).astype(np.int32)
    gt = labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    return correct / total, correct, total


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    aa = (np.asarray(a) & 1).astype(bool)
    bb = (np.asarray(b) & 1).astype(bool)
    inter = np.logical_and(aa, bb).sum()
    union = np.logical_or(aa, bb).sum()
    return float(inter / union) if union else 1.0


def score_method(
    name: str,
    train_hvs: np.ndarray,
    train_labels: np.ndarray,
    protos: np.ndarray,
) -> np.ndarray:
    y = train_labels.astype(np.int32)
    if name == "fisher":
        return per_bit_fisher_scores(train_hvs, y)
    if name == "variance":
        return per_bit_variance_scores(train_hvs, y)
    if name == "mutual_information":
        return per_bit_mutual_information_scores(train_hvs, y)
    if name == "class_mean_separation":
        return per_bit_class_mean_separation_scores(train_hvs, y)
    if name == "prototype_disagreement":
        return per_bit_prototype_disagreement_scores(protos)
    if name == "entropy":
        return per_bit_entropy_scores(train_hvs, y)
    raise ValueError(f"not an informed scoring method: {name}")


def eval_subject(
    subject: int,
    D: int,
    cnt_w: int,
    item_mem_seed: int,
    keep_ratio: float,
    methods: Sequence[str],
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
    cap_rng = np.random.default_rng(seed + 1000 * subject + item_mem_seed)
    if max_train_windows is not None and train_q.shape[0] > max_train_windows:
        train_q, train_labels = cap_windows_random(
            train_q, train_labels, max_train_windows, rng=cap_rng
        )
    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q, test_labels = cap_windows_random(
            test_q, test_labels, max_test_windows, rng=cap_rng
        )

    cfg = hdc_cfg_for_d(D, item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    n_keep = max(1, int(round(D * keep_ratio)))

    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]} "
        f"item_mem_seed={item_mem_seed} n_keep={n_keep}",
        flush=True,
    )
    train_hvs = encode_queries(engine, mem, cfg, train_q, cnt_w, f"s{subject}/train")
    test_hvs = encode_queries(engine, mem, cfg, test_q, cnt_w, f"s{subject}/test")
    protos = train_prototypes_from_hvs(train_hvs, train_labels, cfg)

    support_mask = active_bit_mask(np.vstack([train_hvs, test_hvs]))
    active = int(support_mask.sum())

    full_mask = np.ones(cfg.D, dtype=np.uint8)
    full_acc, full_correct, n_test = accuracy_with_mask(
        test_hvs, test_labels, protos, full_mask
    )

    fisher_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))
    fisher_mask = mask_topk_from_scores(fisher_scores, n_keep)

    method_rows: Dict[str, dict] = {}
    for name in methods:
        meta = METHOD_META[name]
        t0 = time.perf_counter()
        if meta["kind"] == "informed":
            if name == "fisher":
                scores = fisher_scores
                mask = fisher_mask
            else:
                scores = score_method(name, train_hvs, train_labels, protos)
                mask = mask_topk_from_scores(scores, n_keep)
            acc, correct, _ = accuracy_with_mask(test_hvs, test_labels, protos, mask)
            rank_s = time.perf_counter() - t0
            method_rows[name] = {
                "accuracy": acc,
                "correct": correct,
                "n_test": n_test,
                "n_keep": int(mask.sum()),
                "jaccard_vs_fisher": jaccard(mask, fisher_mask),
                "ranking_wall_s": round(rank_s, 4),
                "ranking_cost": meta["ranking_cost"],
                "requires_retraining": meta["requires_retraining"],
            }
        else:
            # random: average over seeds
            accs = []
            jacs = []
            for rs in random_seeds:
                if name == "random_full":
                    mask = mask_from_scores(
                        fisher_scores,
                        keep_ratio,
                        rng=np.random.default_rng(rs),
                        informed=False,
                    )
                else:
                    mask = mask_random_from_support(
                        support_mask, n_keep, rng=np.random.default_rng(rs)
                    )
                acc, _, _ = accuracy_with_mask(test_hvs, test_labels, protos, mask)
                accs.append(acc)
                jacs.append(jaccard(mask, fisher_mask))
            rank_s = time.perf_counter() - t0
            mean_acc = float(np.mean(accs))
            method_rows[name] = {
                "accuracy": mean_acc,
                "accuracy_std": float(np.std(accs)) if len(accs) > 1 else 0.0,
                "accuracy_by_seed": [
                    {"seed": int(rs), "accuracy": float(a)}
                    for rs, a in zip(random_seeds, accs)
                ],
                "n_test": n_test,
                "n_keep": n_keep,
                "jaccard_vs_fisher_mean": float(np.mean(jacs)),
                "ranking_wall_s": round(rank_s, 4),
                "ranking_cost": meta["ranking_cost"],
                "requires_retraining": meta["requires_retraining"],
            }

    # Fill gap_pp_vs_fisher for all methods now that fisher exists
    fisher_acc = method_rows["fisher"]["accuracy"] if "fisher" in method_rows else full_acc
    for name, row in method_rows.items():
        row["gap_pp_vs_fisher"] = 100.0 * (row["accuracy"] - fisher_acc)

    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "D": D,
        "cnt_w": cnt_w,
        "keep_ratio": keep_ratio,
        "n_keep": n_keep,
        "n_train": int(train_q.shape[0]),
        "n_test": n_test,
        "active_bit_support": active,
        "full_width_accuracy": full_acc,
        "full_width_correct": full_correct,
        "methods": method_rows,
    }


def aggregate(per_subject: List[dict], methods: Sequence[str]) -> List[dict]:
    out = []
    for name in methods:
        meta = METHOD_META[name]
        accs = [g["methods"][name]["accuracy"] for g in per_subject]
        gaps = [g["methods"][name]["gap_pp_vs_fisher"] for g in per_subject]
        jacs = []
        for g in per_subject:
            m = g["methods"][name]
            if "jaccard_vs_fisher" in m:
                jacs.append(m["jaccard_vs_fisher"])
            elif "jaccard_vs_fisher_mean" in m:
                jacs.append(m["jaccard_vs_fisher_mean"])
        out.append(
            {
                "method": name,
                "ranking_cost": meta["ranking_cost"],
                "requires_retraining": meta["requires_retraining"],
                "n_subjects": len(per_subject),
                "spatial_mean_accuracy": float(np.mean(accs)),
                "spatial_std_accuracy": float(np.std(accs)) if len(accs) > 1 else 0.0,
                "spatial_mean_gap_pp_vs_fisher": float(np.mean(gaps)),
                "spatial_mean_jaccard_vs_fisher": float(np.mean(jacs)) if jacs else None,
                "per_subject_accuracy": {
                    str(g["subject"]): g["methods"][name]["accuracy"] for g in per_subject
                },
            }
        )
    return out


def write_csv(path: Path, summary: List[dict]) -> None:
    fields = [
        "method",
        "ranking_cost",
        "requires_retraining",
        "n_subjects",
        "spatial_mean_accuracy",
        "spatial_std_accuracy",
        "spatial_mean_gap_pp_vs_fisher",
        "spatial_mean_jaccard_vs_fisher",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in summary:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, summary: List[dict]) -> None:
    lines = [
        "# Issue 9 — ranking baselines @ 128 bits",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · Engine: **{meta['engine']}**",
        f"D={meta['D']}  keep={meta['keep_ratio']} ({meta['n_keep']} bits)  "
        f"item_mem_seeds={meta['item_mem_seeds']}  subjects={meta['subjects']}",
        f"Test cap: {meta.get('max_test_windows_per_subject') or 'all'} random windows/subject",
        "",
        "## Spatial mean (S1–S5)",
        "",
        "| Method | Acc | Gap vs Fisher (pp) | Jaccard vs Fisher | Cost | Retrain? |",
        "|--------|-----|--------------------|-------------------|------|----------|",
    ]
    # Sort by accuracy descending for readability
    for row in sorted(summary, key=lambda r: -r["spatial_mean_accuracy"]):
        jac = row["spatial_mean_jaccard_vs_fisher"]
        jac_s = f"{jac:.3f}" if jac is not None else "—"
        lines.append(
            f"| {row['method']} | {100.0 * row['spatial_mean_accuracy']:.2f}% | "
            f"{row['spatial_mean_gap_pp_vs_fisher']:+.2f} | {jac_s} | "
            f"{row['ranking_cost']} | {'yes' if row['requires_retraining'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Informed methods rank TRAIN-encoded bits; random methods average "
            f"{len(meta['random_seeds'])} seeds.",
            "- `random_active` samples only from positions that vary (#5 fair baseline).",
            "- Learned mask omitted (optional / high cost).",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_ranking_baselines.py --quick",
            "python3 python_ref/run_ranking_baselines.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checkpoint(out_dir: Path, meta: dict, per_subject: List[dict]) -> None:
    path = out_dir / "ranking_baselines_results.partial.json"
    path.write_text(
        json.dumps({"meta": meta, "per_subject": per_subject}, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 9 ranking baselines")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--seeds", type=str, default=None, help="item_mem seeds, e.g. 42")
    p.add_argument("--subjects", type=int, nargs="*", default=None)
    p.add_argument("--max-windows", type=int, default=None)
    p.add_argument("--max-train-windows", type=int, default=None)
    p.add_argument("--random-seeds", type=int, nargs="*", default=None)
    return p.parse_args()


def parse_seeds(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def main() -> int:
    args = parse_args()
    require_dataset()

    sweep_cfg = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    D = int(sweep_cfg["D"])
    cnt_w = int(sweep_cfg["cnt_w"])
    keep_ratio = float(sweep_cfg["keep_ratio"])
    n_keep = max(1, int(round(D * keep_ratio)))
    methods = list(sweep_cfg["methods"])
    for m in methods:
        if m not in METHOD_META:
            raise SystemExit(f"unknown method: {m}")

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
        max_windows = (
            args.max_windows
            if args.max_windows is not None
            else sweep_cfg.get("max_test_windows_per_subject")
        )
        max_train_windows = (
            args.max_train_windows
            if args.max_train_windows is not None
            else sweep_cfg.get("max_train_windows_per_subject")
        )
        random_seeds = args.random_seeds or sweep_cfg["random_seeds"]

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Issue 9 — ranking baselines (hdc_ref / RTL encoder)")
    print(f"  protocol={protocol_id}  D={D}  keep={keep_ratio} ({n_keep} bits)")
    print(f"  methods={methods}")
    print(f"  item_mem_seeds={list(item_mem_seeds)}  subjects={subjects}")
    print(f"  random_seeds={list(random_seeds)}")
    print(f"  max_train={max_train_windows or 'all'}  max_test={max_windows or 'all'}")
    print("=" * 70)

    t0 = time.time()
    per_subject: List[dict] = []
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 9,
        "engine": sweep_cfg.get("engine", "hdc_ref"),
        "protocol": protocol_id,
        "emg_config": str(args.emg_config.relative_to(REPO)),
        "subjects": list(subjects),
        "D": D,
        "cnt_w": cnt_w,
        "keep_ratio": keep_ratio,
        "n_keep": n_keep,
        "item_mem_seeds": list(item_mem_seeds),
        "methods": methods,
        "random_seeds": list(random_seeds),
        "max_train_windows_per_subject": max_train_windows,
        "max_test_windows_per_subject": max_windows,
    }

    for item_mem_seed in item_mem_seeds:
        print(f"\n== item_mem_seed={item_mem_seed} ==", flush=True)
        for subject in subjects:
            print(f"\n== subject {subject} ==", flush=True)
            row = eval_subject(
                int(subject),
                D,
                cnt_w,
                int(item_mem_seed),
                keep_ratio,
                methods,
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

    summary = aggregate(per_subject, methods)
    meta["elapsed_s"] = round(time.time() - t0, 1)
    meta["summary"] = summary

    out_json = args.out_dir / "ranking_baselines_results.json"
    out_json.write_text(
        json.dumps({"meta": meta, "per_subject": per_subject}, indent=2),
        encoding="utf-8",
    )
    write_csv(args.out_dir / "ranking_baselines_summary.csv", summary)
    write_readme(args.out_dir / "README.md", meta, summary)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    for row in sorted(summary, key=lambda r: -r["spatial_mean_accuracy"]):
        print(
            f"  {row['method']:28s} acc={100.0 * row['spatial_mean_accuracy']:.2f}% "
            f"gap_vs_fisher={row['spatial_mean_gap_pp_vs_fisher']:+.2f}pp"
        )
    print(f"Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
