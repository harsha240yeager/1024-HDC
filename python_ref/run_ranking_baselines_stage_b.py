#!/usr/bin/env python3
"""
Issue #22 — ranking baselines on Stage B BSC encoder at keep=128 bits.

Same six informed criteria as issue #9 (hdc_ref), plus random full/active,
using the literature Stage B spatial encoder (~89% unpruned) under HDC-2.

Usage (from repo root):
  python3 python_ref/run_ranking_baselines_stage_b.py --quick
  python3 python_ref/run_ranking_baselines_stage_b.py

Outputs:
  results/protocol_v2/twist1_stage_b/ranking_baselines_results.json
  results/protocol_v2/twist1_stage_b/ranking_baselines_summary.csv
  results/protocol_v2/twist1_stage_b/ranking_baselines_README.md
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from export_emg_board_vectors import require_dataset  # noqa: E402
from hdc_ref import (  # noqa: E402
    active_bit_mask,
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
from run_ranking_baselines import METHOD_META, jaccard, score_method  # noqa: E402
from stage_b_engine import (  # noqa: E402
    N_CLASS,
    StageBConfig,
    StageBEngine,
    load_json,
    split_config_from_emg,
    split_subject_hdc2,
)

DEFAULT_CFG = HERE / "config" / "ranking_baselines_stage_b.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "twist1_stage_b"


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
    idx = np.array(picks[:n_max], dtype=np.int64)
    return q[idx], labels[idx]


def eval_with_mask(
    engine: StageBEngine,
    test_hvs: np.ndarray,
    test_labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
    *,
    progress_label: str = "",
) -> Tuple[float, int, int, np.ndarray]:
    gt = test_labels.astype(np.int32) - 1
    preds = engine.classify_batch(test_hvs, protos, mask, progress_label=progress_label)
    correct = int((preds == gt).sum())
    total = int(test_labels.shape[0])
    acc = correct / total if total else 0.0
    return acc, correct, total, preds


def eval_subject(
    subject: int,
    D: int,
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
    train_q, train_labels, test_q, test_labels = split_subject_hdc2(
        subject, seed=seed, train_frac=train_frac, split_kw=split_kw
    )
    if max_train_windows is not None and train_q.shape[0] > max_train_windows:
        train_q, train_labels = cap_windows_stratified(train_q, train_labels, max_train_windows)
    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q, test_labels = cap_windows_stratified(test_q, test_labels, max_test_windows)

    n_keep = max(1, int(round(D * keep_ratio)))
    cfg = StageBConfig(D=D, item_mem_seed=item_mem_seed)
    engine = StageBEngine(cfg)

    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]} "
        f"n_keep={n_keep}",
        flush=True,
    )

    train_hvs = engine.encode_quantized(train_q)
    test_hvs = engine.encode_quantized(test_q)
    protos = engine.train_prototypes(train_hvs, train_labels)

    support_mask = active_bit_mask(np.vstack([train_hvs, test_hvs]))
    active = int(support_mask.sum())

    full_mask = np.ones(D, dtype=np.uint8)
    full_acc, full_correct, n_test, _ = eval_with_mask(
        engine, test_hvs, test_labels, protos, full_mask, progress_label=f"s{subject}/full"
    )

    y = train_labels.astype(np.int32)
    fisher_scores = per_bit_fisher_scores(train_hvs, y)
    fisher_mask = mask_topk_from_scores(fisher_scores, n_keep)
    _, _, _, fisher_preds = eval_with_mask(
        engine, test_hvs, test_labels, protos, fisher_mask, progress_label=f"s{subject}/fisher"
    )

    method_rows: Dict[str, dict] = {}
    for name in methods:
        meta = METHOD_META[name]
        t0 = time.perf_counter()
        if meta["kind"] == "informed":
            if name == "fisher":
                mask = fisher_mask
            else:
                scores = score_method(name, train_hvs, train_labels, protos)
                mask = mask_topk_from_scores(scores, n_keep)
            acc, correct, _, preds = eval_with_mask(
                engine,
                test_hvs,
                test_labels,
                protos,
                mask,
                progress_label=f"s{subject}/{name}",
            )
            agree = float((preds == fisher_preds).mean()) if n_test else 1.0
            rank_s = time.perf_counter() - t0
            method_rows[name] = {
                "accuracy": acc,
                "correct": correct,
                "n_test": n_test,
                "n_keep": int(mask.sum()),
                "jaccard_vs_fisher": jaccard(mask, fisher_mask),
                "prediction_agreement_vs_fisher": agree,
                "ranking_wall_s": round(rank_s, 4),
                "ranking_cost": meta["ranking_cost"],
                "requires_retraining": meta["requires_retraining"],
            }
        else:
            accs = []
            jacs = []
            agrees = []
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
                acc, _, _, preds = eval_with_mask(
                    engine,
                    test_hvs,
                    test_labels,
                    protos,
                    mask,
                    progress_label=f"s{subject}/{name}{rs}",
                )
                accs.append(acc)
                jacs.append(jaccard(mask, fisher_mask))
                agrees.append(float((preds == fisher_preds).mean()) if n_test else 1.0)
            rank_s = time.perf_counter() - t0
            method_rows[name] = {
                "accuracy": float(np.mean(accs)),
                "accuracy_std": float(np.std(accs)) if len(accs) > 1 else 0.0,
                "accuracy_by_seed": [
                    {"seed": int(rs), "accuracy": float(a)}
                    for rs, a in zip(random_seeds, accs)
                ],
                "n_test": n_test,
                "n_keep": n_keep,
                "jaccard_vs_fisher_mean": float(np.mean(jacs)),
                "prediction_agreement_vs_fisher_mean": float(np.mean(agrees)),
                "ranking_wall_s": round(rank_s, 4),
                "ranking_cost": meta["ranking_cost"],
                "requires_retraining": meta["requires_retraining"],
            }

    fisher_acc = method_rows["fisher"]["accuracy"] if "fisher" in method_rows else full_acc
    for name, row in method_rows.items():
        row["gap_pp_vs_fisher"] = 100.0 * (row["accuracy"] - fisher_acc)

    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "D": D,
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
        agrees = []
        for g in per_subject:
            m = g["methods"][name]
            if "jaccard_vs_fisher" in m:
                jacs.append(m["jaccard_vs_fisher"])
            elif "jaccard_vs_fisher_mean" in m:
                jacs.append(m["jaccard_vs_fisher_mean"])
            if "prediction_agreement_vs_fisher" in m:
                agrees.append(m["prediction_agreement_vs_fisher"])
            elif "prediction_agreement_vs_fisher_mean" in m:
                agrees.append(m["prediction_agreement_vs_fisher_mean"])
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
                "spatial_mean_prediction_agreement_vs_fisher": (
                    float(np.mean(agrees)) if agrees else None
                ),
                "per_subject_accuracy": {
                    str(g["subject"]): g["methods"][name]["accuracy"] for g in per_subject
                },
            }
        )
    return out


def jaccard_range(summary: List[dict], *, informed_only: bool = False) -> Tuple[float, float]:
    jacs = []
    for row in summary:
        if row["method"] == "fisher":
            continue
        if informed_only and METHOD_META[row["method"]]["kind"] != "informed":
            continue
        jac = row["spatial_mean_jaccard_vs_fisher"]
        if jac is not None:
            jacs.append(jac)
    if not jacs:
        return 0.0, 1.0
    return float(min(jacs)), float(max(jacs))


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
        "spatial_mean_prediction_agreement_vs_fisher",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in summary:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, summary: List[dict]) -> None:
    jac_lo, jac_hi = meta["jaccard_vs_fisher_range_informed"]
    informed = [r for r in summary if METHOD_META[r["method"]]["kind"] == "informed"]
    informed_gaps = [abs(r["spatial_mean_gap_pp_vs_fisher"]) for r in informed if r["method"] != "fisher"]
    max_informed_gap = max(informed_gaps) if informed_gaps else 0.0
    tie = max_informed_gap < 0.01

    lines = [
        "# Issue 22 — Stage B ranking baselines @ 128 bits",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · Engine: **{meta['engine']}**",
        f"D={meta['D']}  keep={meta['keep_ratio']} ({meta['n_keep']} bits)  "
        f"item_mem_seed={meta['item_mem_seed']}  subjects={meta['subjects']}",
        f"Mean active bit support: **{meta['mean_active_bit_support']:.0f}** / {meta['D']}",
        "",
        "## Spatial mean (S1–S5)",
        "",
        "| Method | Acc | Gap vs Fisher (pp) | Jaccard vs Fisher | Pred agree vs Fisher | Cost |",
        "|--------|-----|--------------------|-------------------|----------------------|------|",
    ]
    for row in sorted(summary, key=lambda r: -r["spatial_mean_accuracy"]):
        jac = row["spatial_mean_jaccard_vs_fisher"]
        agree = row["spatial_mean_prediction_agreement_vs_fisher"]
        jac_s = f"{jac:.3f}" if jac is not None else "—"
        agree_s = f"{100.0 * agree:.2f}%" if agree is not None else "—"
        lines.append(
            f"| {row['method']} | {100.0 * row['spatial_mean_accuracy']:.2f}% | "
            f"{row['spatial_mean_gap_pp_vs_fisher']:+.2f} | {jac_s} | {agree_s} | "
            f"{row['ranking_cost']} |"
        )

    lines.extend(
        [
            "",
            f"**Jaccard vs Fisher (informed methods, excl. Fisher):** {jac_lo:.3f} – {jac_hi:.3f}",
            "",
            "## Dense-support conclusion (Sec. V-D extension)",
            "",
        ]
    )
    if tie:
        lines.append(
            "On the **Stage B** encoder (~"
            f"{100.0 * meta.get('mean_full_width_accuracy', 0):.1f}% unpruned, "
            f"~{meta['mean_active_bit_support']:.0f} active bits), all six informed "
            "ranking criteria **still tie in spatial mean accuracy** at keep=128 — the "
            "same pattern as hdc_ref under sparse support. Mask Jaccard vs Fisher spans "
            f"**{jac_lo:.2f}–{jac_hi:.2f}**, so criteria **diverge in bit choice** but "
            "not in classification outcome. The iso-density story remains "
            "**informed vs random**, not Fisher-unique; dense support does not unlock "
            "criterion-specific accuracy gains at fixed K."
        )
    else:
        lines.append(
            "On the **Stage B** encoder (~"
            f"{100.0 * meta.get('mean_full_width_accuracy', 0):.1f}% unpruned, "
            f"~{meta['mean_active_bit_support']:.0f} active bits), informed ranking "
            f"criteria **separate in accuracy** at keep=128 (max |gap| vs Fisher = "
            f"{max_informed_gap:.2f} pp). Mask Jaccard vs Fisher spans "
            f"**{jac_lo:.2f}–{jac_hi:.2f}**. Dense support changes which criterion "
            "wins at fixed K — contrast with hdc_ref where all informed methods tied."
        )

    lines.extend(
        [
            "",
            "Compare sparse encoder: [`ranking_baselines/`](../ranking_baselines/) (issue #9).",
            "Stage B iso-density: [`README.md`](README.md) (issue #21).",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_ranking_baselines_stage_b.py --quick",
            "python3 python_ref/run_ranking_baselines_stage_b.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 22 Stage B ranking baselines")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
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
    keep_ratio = float(sweep_cfg["keep_ratio"])
    n_keep = max(1, int(round(D * keep_ratio)))
    methods = list(sweep_cfg["methods"])
    item_mem_seed = int(sweep_cfg["item_mem_seed"])

    for m in methods:
        if m not in METHOD_META:
            raise SystemExit(f"unknown method: {m}")

    if args.quick:
        q = sweep_cfg["quick"]
        subjects = args.subjects or q.get("subjects") or sweep_cfg["subjects"]
        max_windows = q.get("max_test_windows_per_subject")
        max_train_windows = q.get("max_train_windows_per_subject")
        random_seeds = args.random_seeds or q.get("random_seeds") or sweep_cfg["random_seeds"]
    else:
        subjects = args.subjects or sweep_cfg["subjects"]
        max_windows = args.max_windows if args.max_windows is not None else sweep_cfg.get(
            "max_test_windows_per_subject"
        )
        max_train_windows = (
            args.max_train_windows
            if args.max_train_windows is not None
            else sweep_cfg.get("max_train_windows_per_subject")
        )
        random_seeds = args.random_seeds or sweep_cfg["random_seeds"]

    seed, train_frac, split_kw, _ = split_config_from_emg(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Issue 22 — Stage B ranking baselines")
    print(f"  protocol={protocol_id}  D={D}  keep={keep_ratio} ({n_keep} bits)")
    print(f"  methods={methods}")
    print(f"  item_mem_seed={item_mem_seed}  subjects={subjects}")
    print(f"  random_seeds={list(random_seeds)}")
    print(f"  max_train={max_train_windows or 'all'}  max_test={max_windows or 'all'}")
    print("=" * 70)

    t0 = time.time()
    per_subject: List[dict] = []

    for subject in subjects:
        print(f"\n== subject {subject} ==", flush=True)
        row = eval_subject(
            int(subject),
            D,
            item_mem_seed,
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
        partial = args.out_dir / "ranking_baselines_results.partial.json"
        partial.write_text(
            json.dumps({"status": "running", "per_subject": per_subject}, indent=2),
            encoding="utf-8",
        )

    summary = aggregate(per_subject, methods)
    jac_lo, jac_hi = jaccard_range(summary, informed_only=True)
    jac_lo_all, jac_hi_all = jaccard_range(summary, informed_only=False)
    mean_active = float(np.mean([g["active_bit_support"] for g in per_subject]))
    mean_full = float(np.mean([g["full_width_accuracy"] for g in per_subject]))

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 22,
        "engine": sweep_cfg.get("engine", "stage_b_bsc"),
        "protocol": protocol_id,
        "emg_config": str(args.emg_config.relative_to(REPO)),
        "subjects": list(subjects),
        "D": D,
        "keep_ratio": keep_ratio,
        "n_keep": n_keep,
        "item_mem_seed": item_mem_seed,
        "methods": methods,
        "random_seeds": list(random_seeds),
        "max_train_windows_per_subject": max_train_windows,
        "max_test_windows_per_subject": max_windows,
        "elapsed_s": round(time.time() - t0, 1),
        "mean_active_bit_support": mean_active,
        "mean_full_width_accuracy": mean_full,
        "jaccard_vs_fisher_range_informed": [jac_lo, jac_hi],
        "jaccard_vs_fisher_range_all": [jac_lo_all, jac_hi_all],
        "summary": summary,
    }

    out_json = args.out_dir / "ranking_baselines_results.json"
    out_json.write_text(json.dumps({"meta": meta, "per_subject": per_subject}, indent=2), encoding="utf-8")
    write_csv(args.out_dir / "ranking_baselines_summary.csv", summary)
    write_readme(args.out_dir / "ranking_baselines_README.md", meta, summary)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s  active_support≈{mean_active:.0f}")
    print(f"Jaccard vs Fisher range: {jac_lo:.3f} – {jac_hi:.3f}")
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
