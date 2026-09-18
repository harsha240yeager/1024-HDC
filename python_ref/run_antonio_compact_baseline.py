#!/usr/bin/env python3
"""
Issue #39 — Antonio & Alvarez (ISCAS 2022) identical-across-prototypes compaction.

Drop bits that are identical on all TRAIN class prototypes; classify with the
remaining mask (no Fisher ranking). Compare to Fisher-128, active support, and
support-restricted random @128 on HDC-2 (hdc_ref and Stage B encoders).

Usage (from repo root):
  python3 python_ref/run_antonio_compact_baseline.py --quick
  python3 python_ref/run_antonio_compact_baseline.py
  python3 python_ref/run_antonio_compact_baseline.py --engine stage_b

Outputs:
  results/protocol_v2/antonio_compact/antonio_compact_results.json
  results/protocol_v2/antonio_compact/antonio_compact_summary.csv
  results/protocol_v2/antonio_compact/README.md
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
    antonio_identical_compact_mask,
    bundle_majority_unlimited,
    mask_random_from_support,
    mask_topk_from_scores,
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
from run_ranking_baselines import jaccard  # noqa: E402
from stage_b_engine import (  # noqa: E402
    StageBConfig,
    StageBEngine,
    split_subject_hdc2,
)

DEFAULT_CFG = HERE / "config" / "antonio_compact.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "antonio_compact"


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


def encode_queries_hdc(
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


def predict_with_mask(
    queries: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    m = (np.asarray(mask, dtype=np.uint8) & 1).reshape(1, -1)
    q = np.asarray(queries, dtype=np.uint8)
    p = np.asarray(protos, dtype=np.uint8)
    dists = np.stack([((q ^ p[k]) & m).sum(axis=1) for k in range(p.shape[0])], axis=1)
    return dists.argmin(axis=1).astype(np.int32)


def accuracy_and_preds(
    queries: np.ndarray,
    labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> Tuple[float, int, int, np.ndarray]:
    total = int(labels.shape[0])
    if total == 0:
        return 0.0, 0, 0, np.zeros(0, dtype=np.int32)
    pred = predict_with_mask(queries, protos, mask)
    gt = labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    return correct / total, correct, total, pred


def pred_agreement(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0:
        return 1.0
    return float(np.mean(a == b))


def eval_masks_common(
    *,
    D: int,
    keep_ratio: float,
    random_seeds: Sequence[int],
    train_hvs: np.ndarray,
    train_labels: np.ndarray,
    test_hvs: np.ndarray,
    test_labels: np.ndarray,
    protos: np.ndarray,
    classify_fn,
) -> dict:
    """Shared mask metrics; classify_fn(mask) -> (acc, correct, n_test, preds)."""
    n_keep_fisher = max(1, int(round(D * keep_ratio)))
    support_mask = active_bit_mask(np.vstack([train_hvs, test_hvs]))
    n_active = int(support_mask.sum())

    full_mask = np.ones(D, dtype=np.uint8)
    full_acc, full_correct, n_test, full_pred = classify_fn(full_mask)

    antonio_mask = antonio_identical_compact_mask(protos)
    n_keep_antonio = int(antonio_mask.sum())
    n_identical = D - n_keep_antonio

    fisher_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))
    fisher_mask = mask_topk_from_scores(fisher_scores, n_keep_fisher)

    ant_acc, ant_correct, _, ant_pred = classify_fn(antonio_mask)
    fish_acc, fish_correct, _, fish_pred = classify_fn(fisher_mask)

    rand_accs: List[float] = []
    rand_jac_antonio: List[float] = []
    rand_jac_fisher: List[float] = []
    for rs in random_seeds:
        rmask = mask_random_from_support(
            support_mask, n_keep_fisher, rng=np.random.default_rng(rs)
        )
        acc, _, _, _ = classify_fn(rmask)
        rand_accs.append(acc)
        rand_jac_antonio.append(jaccard(rmask, antonio_mask))
        rand_jac_fisher.append(jaccard(rmask, fisher_mask))

    return {
        "n_test": n_test,
        "n_active_bit_support": n_active,
        "n_identical_across_prototypes": n_identical,
        "n_keep_antonio": n_keep_antonio,
        "n_keep_fisher": int(fisher_mask.sum()),
        "full_width": {
            "accuracy": full_acc,
            "correct": full_correct,
        },
        "antonio_identical_compact": {
            "accuracy": ant_acc,
            "correct": ant_correct,
            "gap_pp_vs_full": 100.0 * (ant_acc - full_acc),
            "gap_pp_vs_fisher": 100.0 * (ant_acc - fish_acc),
            "pred_agreement_vs_full": pred_agreement(ant_pred, full_pred),
            "pred_agreement_vs_fisher": pred_agreement(ant_pred, fish_pred),
        },
        "fisher_128": {
            "accuracy": fish_acc,
            "correct": fish_correct,
            "gap_pp_vs_full": 100.0 * (fish_acc - full_acc),
        },
        "random_active_at_fisher_width": {
            "n_keep": n_keep_fisher,
            "accuracy_mean": float(np.mean(rand_accs)),
            "accuracy_std": float(np.std(rand_accs)) if len(rand_accs) > 1 else 0.0,
            "accuracy_by_seed": [
                {"seed": int(rs), "accuracy": float(a)}
                for rs, a in zip(random_seeds, rand_accs)
            ],
            "gap_pp_vs_fisher_mean": 100.0 * (float(np.mean(rand_accs)) - fish_acc),
        },
        "jaccard": {
            "antonio_vs_fisher": jaccard(antonio_mask, fisher_mask),
            "antonio_vs_active_support": jaccard(antonio_mask, support_mask),
            "fisher_vs_active_support": jaccard(fisher_mask, support_mask),
            "random_active_vs_antonio_mean": float(np.mean(rand_jac_antonio)),
            "random_active_vs_fisher_mean": float(np.mean(rand_jac_fisher)),
        },
    }


def eval_subject_hdc_ref(
    subject: int,
    D: int,
    cnt_w: int,
    item_mem_seed: int,
    keep_ratio: float,
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

    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]} "
        f"item_mem_seed={item_mem_seed}",
        flush=True,
    )
    train_hvs = encode_queries_hdc(engine, mem, cfg, train_q, cnt_w, f"s{subject}/train")
    test_hvs = encode_queries_hdc(engine, mem, cfg, test_q, cnt_w, f"s{subject}/test")
    protos = train_prototypes_from_hvs(train_hvs, train_labels, cfg)

    def classify_fn(mask: np.ndarray):
        return accuracy_and_preds(test_hvs, test_labels, protos, mask)

    metrics = eval_masks_common(
        D=D,
        keep_ratio=keep_ratio,
        random_seeds=random_seeds,
        train_hvs=train_hvs,
        train_labels=train_labels,
        test_hvs=test_hvs,
        test_labels=test_labels,
        protos=protos,
        classify_fn=classify_fn,
    )
    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "n_train": int(train_q.shape[0]),
        **metrics,
    }


def eval_subject_stage_b(
    subject: int,
    D: int,
    item_mem_seed: int,
    keep_ratio: float,
    random_seeds: Sequence[int],
    seed: int,
    train_frac: float,
    max_test_windows: Optional[int],
    max_train_windows: Optional[int],
    split_kw: dict,
) -> dict:
    train_q, train_labels, test_q, test_labels = split_subject_hdc2(
        subject, seed=seed, train_frac=train_frac, split_kw=split_kw
    )
    cap_rng = np.random.default_rng(seed + 2000 * subject + item_mem_seed)
    if max_train_windows is not None and train_q.shape[0] > max_train_windows:
        train_q, train_labels = cap_windows_random(
            train_q, train_labels, max_train_windows, rng=cap_rng
        )
    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q, test_labels = cap_windows_random(
            test_q, test_labels, max_test_windows, rng=cap_rng
        )

    cfg = StageBConfig(D=D, item_mem_seed=item_mem_seed)
    engine = StageBEngine(cfg)

    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]} "
        f"item_mem_seed={item_mem_seed}",
        flush=True,
    )
    train_hvs = engine.encode_quantized(train_q)
    test_hvs = engine.encode_quantized(test_q)
    protos = engine.train_prototypes(train_hvs, train_labels)

    def classify_fn(mask: np.ndarray):
        acc, correct, n_test, pred = accuracy_and_preds(test_hvs, test_labels, protos, mask)
        return acc, correct, n_test, pred

    metrics = eval_masks_common(
        D=D,
        keep_ratio=keep_ratio,
        random_seeds=random_seeds,
        train_hvs=train_hvs,
        train_labels=train_labels,
        test_hvs=test_hvs,
        test_labels=test_labels,
        protos=protos,
        classify_fn=classify_fn,
    )
    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "n_train": int(train_q.shape[0]),
        **metrics,
    }


def aggregate_engine(per_subject: List[dict]) -> dict:
    def spatial(key_path: Sequence[str]) -> float:
        vals = []
        for row in per_subject:
            cur: object = row
            for k in key_path:
                cur = cur[k]  # type: ignore[index]
            vals.append(float(cur))
        return float(np.mean(vals))

    def pooled(method: str) -> float:
        correct = sum(row[method]["correct"] for row in per_subject)
        n_test = sum(row["n_test"] for row in per_subject)
        return correct / n_test if n_test else 0.0

    rand_mean = spatial(["random_active_at_fisher_width", "accuracy_mean"])
    fish_spatial = spatial(["fisher_128", "accuracy"])
    return {
        "n_subjects": len(per_subject),
        "spatial_mean_n_keep_antonio": spatial(["n_keep_antonio"]),
        "spatial_mean_n_active_support": spatial(["n_active_bit_support"]),
        "spatial_mean_full_accuracy": spatial(["full_width", "accuracy"]),
        "spatial_mean_antonio_accuracy": spatial(["antonio_identical_compact", "accuracy"]),
        "spatial_mean_fisher_accuracy": fish_spatial,
        "spatial_mean_random_active_accuracy": rand_mean,
        "pooled_full_accuracy": pooled("full_width"),
        "pooled_antonio_accuracy": pooled("antonio_identical_compact"),
        "pooled_fisher_accuracy": pooled("fisher_128"),
        "spatial_mean_gap_pp_antonio_vs_fisher": spatial(
            ["antonio_identical_compact", "gap_pp_vs_fisher"]
        ),
        "spatial_mean_gap_pp_antonio_vs_full": spatial(
            ["antonio_identical_compact", "gap_pp_vs_full"]
        ),
        "spatial_mean_jaccard_antonio_vs_fisher": spatial(["jaccard", "antonio_vs_fisher"]),
        "spatial_mean_jaccard_antonio_vs_active": spatial(
            ["jaccard", "antonio_vs_active_support"]
        ),
        "spatial_mean_jaccard_fisher_vs_active": spatial(
            ["jaccard", "fisher_vs_active_support"]
        ),
        "spatial_mean_pred_agreement_antonio_vs_fisher": spatial(
            ["antonio_identical_compact", "pred_agreement_vs_fisher"]
        ),
        "per_subject": {
            str(row["subject"]): {
                "n_keep_antonio": row["n_keep_antonio"],
                "antonio_accuracy": row["antonio_identical_compact"]["accuracy"],
                "fisher_accuracy": row["fisher_128"]["accuracy"],
                "full_accuracy": row["full_width"]["accuracy"],
            }
            for row in per_subject
        },
    }


def write_csv(path: Path, rows: List[dict]) -> None:
    fields = [
        "engine",
        "spatial_mean_antonio_accuracy",
        "spatial_mean_fisher_accuracy",
        "spatial_mean_random_active_accuracy",
        "spatial_mean_full_accuracy",
        "pooled_antonio_accuracy",
        "pooled_fisher_accuracy",
        "spatial_mean_n_keep_antonio",
        "spatial_mean_n_active_support",
        "spatial_mean_jaccard_antonio_vs_fisher",
        "spatial_mean_gap_pp_antonio_vs_fisher",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, summaries: List[dict]) -> None:
    lines = [
        "# Issue 39 — Antonio identical-across-prototypes compact baseline",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}**",
        f"D={meta['D']}  Fisher keep={meta['keep_ratio']} ({meta['n_keep_fisher']} bits)",
        f"Subjects: {meta['subjects']}",
        f"Test cap: {meta.get('max_test_windows_per_subject') or 'all'} windows/subject",
        "",
        "## Summary (spatial mean over S1–S5)",
        "",
        "| Engine | Full | Antonio | Fisher-128 | Random@128 (active) | n_keep Antonio | J(A,F) | Δ Antonio−Fisher (pp) |",
        "|--------|------|---------|------------|---------------------|----------------|--------|----------------------|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['engine']} | {100*s['spatial_mean_full_accuracy']:.2f}% | "
            f"{100*s['spatial_mean_antonio_accuracy']:.2f}% | "
            f"{100*s['spatial_mean_fisher_accuracy']:.2f}% | "
            f"{100*s['spatial_mean_random_active_accuracy']:.2f}% | "
            f"{s['spatial_mean_n_keep_antonio']:.0f} | "
            f"{s['spatial_mean_jaccard_antonio_vs_fisher']:.3f} | "
            f"{s['spatial_mean_gap_pp_antonio_vs_fisher']:+.2f} |"
        )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "- **Antonio:** mask = bits where class TRAIN prototypes are *not* all identical.",
            "- **Fisher-128:** top 128 TRAIN Fisher scores (same density as paper).",
            "- **Random@128:** uniform on active support, averaged over random seeds.",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_antonio_compact_baseline.py --quick",
            "python3 python_ref/run_antonio_compact_baseline.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_engine(
    engine_name: str,
    *,
    subjects: Sequence[int],
    item_mem_seed: int,
    D: int,
    cnt_w: int,
    keep_ratio: float,
    random_seeds: Sequence[int],
    seed: int,
    train_frac: float,
    max_test: Optional[int],
    max_train: Optional[int],
    split_kw: dict,
    out_dir: Path,
    meta_base: dict,
) -> Tuple[List[dict], dict]:
    per_subject: List[dict] = []
    t0 = time.time()
    for subject in subjects:
        print(f"\n== {engine_name} subject {subject} ==", flush=True)
        if engine_name == "hdc_ref":
            row = eval_subject_hdc_ref(
                int(subject),
                D,
                cnt_w,
                item_mem_seed,
                keep_ratio,
                random_seeds,
                seed,
                train_frac,
                max_test,
                max_train,
                split_kw,
            )
        elif engine_name == "stage_b":
            row = eval_subject_stage_b(
                int(subject),
                D,
                item_mem_seed,
                keep_ratio,
                random_seeds,
                seed,
                train_frac,
                max_test,
                max_train,
                split_kw,
            )
        else:
            raise ValueError(engine_name)
        per_subject.append(row)
        partial = {
            "meta": {**meta_base, "elapsed_s": round(time.time() - t0, 1)},
            "engines": {engine_name: {"per_subject": per_subject}},
        }
        (out_dir / "antonio_compact_results.partial.json").write_text(
            json.dumps(partial, indent=2), encoding="utf-8"
        )
    summary = aggregate_engine(per_subject)
    summary["engine"] = engine_name
    summary["item_mem_seed"] = item_mem_seed
    summary["elapsed_s"] = round(time.time() - t0, 1)
    return per_subject, summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 39 Antonio compact baseline")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument(
        "--engine",
        choices=("hdc_ref", "stage_b", "all"),
        default="all",
        help="which encoder(s) to run",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    sweep = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    D = int(sweep["D"])
    cnt_w = int(sweep.get("cnt_w", 6))
    keep_ratio = float(sweep["keep_ratio"])
    n_keep_fisher = max(1, int(round(D * keep_ratio)))

    if args.quick:
        q = sweep["quick"]
        engines = q.get("engines") or sweep["engines"]
        subjects = q.get("subjects") or sweep["subjects"]
        max_test = q.get("max_test_windows_per_subject")
        max_train = q.get("max_train_windows_per_subject")
        random_seeds = q.get("random_seeds") or sweep["random_seeds"]
    else:
        engines = sweep["engines"]
        subjects = sweep["subjects"]
        max_test = sweep.get("max_test_windows_per_subject")
        max_train = sweep.get("max_train_windows_per_subject")
        random_seeds = sweep["random_seeds"]

    if args.engine != "all":
        engines = [args.engine]

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    stage_b_seed = int(sweep.get("stage_b_item_mem_seed", 1))
    hdc_seeds = list(sweep.get("item_mem_seeds", [42]))

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Issue 39 — Antonio identical-across-prototypes baseline")
    print(f"  protocol={protocol_id}  engines={engines}  subjects={subjects}")
    print(f"  max_train={max_train or 'all'}  max_test={max_test or 'all'}")
    print("=" * 70)

    t0 = time.time()
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 39,
        "protocol": protocol_id,
        "emg_config": str(args.emg_config.relative_to(REPO)),
        "subjects": list(subjects),
        "D": D,
        "cnt_w": cnt_w,
        "keep_ratio": keep_ratio,
        "n_keep_fisher": n_keep_fisher,
        "random_seeds": list(random_seeds),
        "max_train_windows_per_subject": max_train,
        "max_test_windows_per_subject": max_test,
        "hdc_ref_item_mem_seeds": hdc_seeds,
        "stage_b_item_mem_seed": stage_b_seed,
    }

    engine_results: Dict[str, dict] = {}
    csv_rows: List[dict] = []

    for eng in engines:
        im_seed = hdc_seeds[0] if eng == "hdc_ref" else stage_b_seed
        if eng == "hdc_ref":
            for im_seed in hdc_seeds:
                key = f"hdc_ref_seed{im_seed}"
                print(f"\n======== {key} ========", flush=True)
                per_sub, summary = run_engine(
                    "hdc_ref",
                    subjects=subjects,
                    item_mem_seed=int(im_seed),
                    D=D,
                    cnt_w=cnt_w,
                    keep_ratio=keep_ratio,
                    random_seeds=random_seeds,
                    seed=seed,
                    train_frac=train_frac,
                    max_test=max_test,
                    max_train=max_train,
                    split_kw=split_kw,
                    out_dir=args.out_dir,
                    meta_base=meta,
                )
                engine_results[key] = {"per_subject": per_sub, "summary": summary}
                csv_rows.append(summary)
        else:
            print(f"\n======== stage_b ========", flush=True)
            per_sub, summary = run_engine(
                "stage_b",
                subjects=subjects,
                item_mem_seed=stage_b_seed,
                D=D,
                cnt_w=cnt_w,
                keep_ratio=keep_ratio,
                random_seeds=random_seeds,
                seed=seed,
                train_frac=train_frac,
                max_test=max_test,
                max_train=max_train,
                split_kw=split_kw,
                out_dir=args.out_dir,
                meta_base=meta,
            )
            engine_results["stage_b"] = {"per_subject": per_sub, "summary": summary}
            csv_rows.append(summary)

    meta["elapsed_s"] = round(time.time() - t0, 1)
    payload = {"meta": meta, "engines": engine_results}
    out_json = args.out_dir / "antonio_compact_results.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(args.out_dir / "antonio_compact_summary.csv", csv_rows)
    write_readme(args.out_dir / "README.md", meta, csv_rows)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    for row in csv_rows:
        print(
            f"  {row['engine']:10s} antonio={100*row['spatial_mean_antonio_accuracy']:.2f}% "
            f"fisher={100*row['spatial_mean_fisher_accuracy']:.2f}% "
            f"n_keep={row['spatial_mean_n_keep_antonio']:.0f} "
            f"J={row['spatial_mean_jaccard_antonio_vs_fisher']:.3f}"
        )
    print(f"Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
