#!/usr/bin/env python3
"""
Issue #5 — active-bit ablation (why only ~200–260 of D bits vary).

On the HDC-2 EMG protocol, for each (subject, item_mem_seed, D):
  - Count active bit support on TRAIN / TEST / pooled encoded windows
  - Diagnose item-memory structure (esp. continuous value table flip path)
  - Compare single-record vs 20-bind bundled support
  - Fisher vs uniform-random vs fair-random-from-active-support @ keep=0.125
  - Show keep=0.5 is lossless whenever n_keep >= active support

Usage (from repo root):
  python3 python_ref/run_active_bit_ablation.py --quick
  python3 python_ref/run_active_bit_ablation.py

Outputs:
  results/protocol_v2/active_bits/active_bit_ablation_results.json
  results/protocol_v2/active_bits/active_bit_ablation_summary.csv
  results/protocol_v2/active_bits/README.md
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

DEFAULT_CFG = HERE / "config" / "active_bit_ablation.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "active_bits"


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
    """
    Uniform random subsample preserving natural class frequencies.

    Equal-per-class capping changes the prior and can shift accuracy by tens of
    points vs the full HDC-2 test pool — do not use it for accuracy claims.
    """
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
    engine: HDCEngine,
    queries: np.ndarray,
    labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> Tuple[float, int, int]:
    del engine  # vectorized path; kept for call-site compatibility
    total = int(labels.shape[0])
    if total == 0:
        return 0.0, 0, 0
    m = (np.asarray(mask, dtype=np.uint8) & 1).reshape(1, -1)
    q = np.asarray(queries, dtype=np.uint8)
    p = np.asarray(protos, dtype=np.uint8)
    # distances[i, k] = masked Hamming(query_i, proto_k)
    dists = np.stack([((q ^ p[k]) & m).sum(axis=1) for k in range(p.shape[0])], axis=1)
    pred = dists.argmin(axis=1).astype(np.int32)
    gt = labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    return correct / total, correct, total


def diagnose_item_memory(mem: ItemMemory, engine: HDCEngine, cfg: HDCConfig) -> dict:
    """Explain sparse support from continuous value ROM + 20-bind bundling."""
    ch_sup = active_bit_support(mem.channel)
    ft_sup = active_bit_support(mem.feature)
    val_sup = active_bit_support(mem.value)
    v_minmax_hamming = int(np.sum(mem.value[0] ^ mem.value[-1]))
    flip_budget = max(1, cfg.D // cfg.n_levels)

    # All single-record binds: 4 channels × 5 features × 16 levels
    records: List[np.ndarray] = []
    for c in range(cfg.n_channels):
        for f in range(cfg.n_features):
            for level in range(cfg.n_levels):
                records.append(engine.encode_record_pair(c, f, level, mem))
    record_hvs = np.stack(records, axis=0)
    record_support = active_bit_support(record_hvs)

    # Per-(c,f) value path: only level changes → how many output bits flip?
    per_slot_support = []
    for c in range(cfg.n_channels):
        for f in range(cfg.n_features):
            slot = np.stack(
                [engine.encode_record_pair(c, f, level, mem) for level in range(cfg.n_levels)],
                axis=0,
            )
            per_slot_support.append(active_bit_support(slot))

    return {
        "channel_table_active_bits": ch_sup,
        "feature_table_active_bits": ft_sup,
        "value_table_active_bits": val_sup,
        "value_minmax_hamming": v_minmax_hamming,
        "value_flip_budget_D_over_levels": flip_budget,
        "n_record_binds": int(record_hvs.shape[0]),
        "single_record_active_support": record_support,
        "per_slot_value_path_active_mean": float(np.mean(per_slot_support)),
        "per_slot_value_path_active_max": int(np.max(per_slot_support)),
        "n_slots": cfg.n_channels * cfg.n_features,
        "note": (
            "Continuous value item memory only walks a Hamming path of length "
            "~D/n_levels between v_min and v_max; each (c,f) slot therefore "
            "can flip at most that many output bits when the level changes. "
            "Twenty-slot majority bundling further collapses weakly contested bits."
        ),
    }


def eval_cell(
    subject: int,
    D: int,
    cnt_w: int,
    item_mem_seed: int,
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
        f"    subject {subject} D={D} seed={item_mem_seed}: "
        f"train={train_q.shape[0]} test={test_q.shape[0]}",
        flush=True,
    )

    diagnosis = diagnose_item_memory(mem, engine, cfg)

    train_hvs = encode_queries(engine, mem, cfg, train_q, cnt_w, f"s{subject}/train")
    test_hvs = encode_queries(engine, mem, cfg, test_q, cnt_w, f"s{subject}/test")
    protos = train_prototypes_from_hvs(train_hvs, train_labels, cfg)

    train_support = active_bit_support(train_hvs)
    test_support = active_bit_support(test_hvs)
    pooled_hvs = np.vstack([train_hvs, test_hvs])
    pooled_support = active_bit_support(pooled_hvs)
    support_mask = active_bit_mask(pooled_hvs)

    # Majority-collapse proxy: compare single-record universe vs bundled windows
    collapse_ratio = (
        float(pooled_support) / float(diagnosis["single_record_active_support"])
        if diagnosis["single_record_active_support"] > 0
        else None
    )

    full_mask = np.ones(cfg.D, dtype=np.uint8)
    full_acc, full_correct, n_test = accuracy_with_mask(
        engine, test_hvs, test_labels, protos, full_mask
    )

    # keep=0.5 (512 @ D=1024): lossless iff n_keep >= active support
    keep_half = 0.5
    n_keep_half = max(1, int(round(D * keep_half)))
    fisher_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))
    half_mask = mask_from_scores(fisher_scores, keep_half, informed=True)
    # Any mask covering all active bits is lossless; Fisher@0.5 usually does
    half_covers_active = bool(np.all(support_mask <= half_mask))
    half_acc, _, _ = accuracy_with_mask(engine, test_hvs, test_labels, protos, half_mask)
    lossless_half = abs(half_acc - full_acc) < 1e-12

    # Gap @ keep=0.125: Fisher vs uniform random vs fair (active-support) random
    n_keep = max(1, int(round(D * gap_keep_ratio)))
    informed_mask = mask_from_scores(fisher_scores, gap_keep_ratio, informed=True)
    informed_acc, informed_correct, _ = accuracy_with_mask(
        engine, test_hvs, test_labels, protos, informed_mask
    )

    uniform_rows = []
    fair_rows = []
    for rs in random_seeds:
        rng = np.random.default_rng(rs)
        uni_mask = mask_from_scores(
            fisher_scores, gap_keep_ratio, rng=rng, informed=False
        )
        fair_mask = mask_random_from_support(support_mask, n_keep, rng=np.random.default_rng(rs + 10_000))
        uni_acc, uni_correct, _ = accuracy_with_mask(
            engine, test_hvs, test_labels, protos, uni_mask
        )
        fair_acc, fair_correct, _ = accuracy_with_mask(
            engine, test_hvs, test_labels, protos, fair_mask
        )
        uniform_rows.append(
            {
                "seed": rs,
                "accuracy": uni_acc,
                "correct": uni_correct,
                "gap_pp_vs_fisher": 100.0 * (informed_acc - uni_acc),
            }
        )
        fair_rows.append(
            {
                "seed": rs,
                "accuracy": fair_acc,
                "correct": fair_correct,
                "n_keep_actual": int(fair_mask.sum()),
                "gap_pp_vs_fisher": 100.0 * (informed_acc - fair_acc),
            }
        )

    uni_mean = float(np.mean([r["accuracy"] for r in uniform_rows]))
    fair_mean = float(np.mean([r["accuracy"] for r in fair_rows]))

    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "D": D,
        "cnt_w": cnt_w,
        "n_train": int(train_q.shape[0]),
        "n_test": n_test,
        "active_bit_support_train": train_support,
        "active_bit_support_test": test_support,
        "active_bit_support_pooled": pooled_support,
        "active_fraction_pooled": float(pooled_support) / float(D),
        "single_record_active_support": diagnosis["single_record_active_support"],
        "majority_collapse_ratio_bundled_over_record": collapse_ratio,
        "diagnosis": diagnosis,
        "full_width_accuracy": full_acc,
        "full_width_correct": full_correct,
        "keep_half": {
            "keep_ratio": keep_half,
            "n_keep": n_keep_half,
            "fisher_accuracy": half_acc,
            "fisher_covers_all_active": half_covers_active,
            "lossless_vs_full_width": lossless_half,
            "active_lt_n_keep": pooled_support <= n_keep_half,
        },
        "gap_keep_ratio": gap_keep_ratio,
        "n_keep_at_gap": n_keep,
        "fisher_accuracy_at_gap": informed_acc,
        "fisher_correct_at_gap": informed_correct,
        "uniform_random_accuracy_mean_at_gap": uni_mean,
        "fair_random_accuracy_mean_at_gap": fair_mean,
        "gap_pp_fisher_minus_uniform": 100.0 * (informed_acc - uni_mean),
        "gap_pp_fisher_minus_fair": 100.0 * (informed_acc - fair_mean),
        "uniform_by_seed": uniform_rows,
        "fair_by_seed": fair_rows,
    }


def aggregate(per_cell: List[dict]) -> List[dict]:
    buckets: Dict[Tuple[int, int], List[dict]] = {}
    for row in per_cell:
        key = (row["item_mem_seed"], row["D"])
        buckets.setdefault(key, []).append(row)

    out = []
    for (item_seed, D), group in sorted(buckets.items()):
        out.append(
            {
                "item_mem_seed": item_seed,
                "D": D,
                "n_subjects": len(group),
                "spatial_mean_active_pooled": float(
                    np.mean([g["active_bit_support_pooled"] for g in group])
                ),
                "spatial_mean_active_train": float(
                    np.mean([g["active_bit_support_train"] for g in group])
                ),
                "spatial_mean_single_record_support": float(
                    np.mean([g["single_record_active_support"] for g in group])
                ),
                "spatial_mean_value_flip_budget": float(
                    np.mean([g["diagnosis"]["value_flip_budget_D_over_levels"] for g in group])
                ),
                "spatial_mean_value_table_active": float(
                    np.mean([g["diagnosis"]["value_table_active_bits"] for g in group])
                ),
                "spatial_mean_full_width_accuracy": float(
                    np.mean([g["full_width_accuracy"] for g in group])
                ),
                "spatial_mean_fisher_at_gap": float(
                    np.mean([g["fisher_accuracy_at_gap"] for g in group])
                ),
                "spatial_mean_uniform_random_at_gap": float(
                    np.mean([g["uniform_random_accuracy_mean_at_gap"] for g in group])
                ),
                "spatial_mean_fair_random_at_gap": float(
                    np.mean([g["fair_random_accuracy_mean_at_gap"] for g in group])
                ),
                "spatial_mean_gap_pp_vs_uniform": float(
                    np.mean([g["gap_pp_fisher_minus_uniform"] for g in group])
                ),
                "spatial_mean_gap_pp_vs_fair": float(
                    np.mean([g["gap_pp_fisher_minus_fair"] for g in group])
                ),
                "all_subjects_keep_half_lossless": all(
                    g["keep_half"]["lossless_vs_full_width"] for g in group
                ),
                "all_subjects_active_lt_keep_half": all(
                    g["keep_half"]["active_lt_n_keep"] for g in group
                ),
            }
        )
    return out


def write_csv(path: Path, summary: List[dict]) -> None:
    fields = [
        "item_mem_seed",
        "D",
        "n_subjects",
        "spatial_mean_active_pooled",
        "spatial_mean_single_record_support",
        "spatial_mean_value_flip_budget",
        "spatial_mean_full_width_accuracy",
        "spatial_mean_fisher_at_gap",
        "spatial_mean_uniform_random_at_gap",
        "spatial_mean_fair_random_at_gap",
        "spatial_mean_gap_pp_vs_uniform",
        "spatial_mean_gap_pp_vs_fair",
        "all_subjects_keep_half_lossless",
        "all_subjects_active_lt_keep_half",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in summary:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, summary: List[dict], per_cell: List[dict]) -> None:
    # Pick a representative diagnosis (first D=1024 or first cell)
    diag = None
    for row in per_cell:
        if row["D"] == 1024:
            diag = row["diagnosis"]
            break
    if diag is None and per_cell:
        diag = per_cell[0]["diagnosis"]

    lines = [
        "# Issue 5 — active-bit ablation",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · Engine: **{meta['engine']}**",
        f"Gap keep={meta['gap_keep_ratio']} ({meta.get('n_keep_at_gap_D1024', '—')} bits @ D=1024)",
        "",
        "## Why support is sparse (~200–260 @ D=1024)",
        "",
    ]
    if diag:
        lines.extend(
            [
                f"- Continuous value item memory flip budget: **D/n_levels = {diag['value_flip_budget_D_over_levels']}**",
                f"- Value table active bits (across 16 levels): **{diag['value_table_active_bits']}**",
                f"- Mean per-(channel,feature) value-path active bits: **{diag['per_slot_value_path_active_mean']:.1f}**",
                f"- Universe of single-record binds active support: **{diag['single_record_active_support']}**",
                f"- After 20-bind majority bundling, window HVs use far fewer positions (see table).",
                "",
                f"> {diag['note']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Spatial means",
            "",
            "| seed | D | Active (pooled) | Single-record | Fisher@gap | Uniform rand | Fair rand | Gap vs uni (pp) | Gap vs fair (pp) | keep=0.5 lossless |",
            "|------|---|-----------------|---------------|------------|--------------|-----------|-----------------|------------------|-------------------|",
        ]
    )
    for row in summary:
        lines.append(
            f"| {row['item_mem_seed']} | {row['D']} | "
            f"{row['spatial_mean_active_pooled']:.0f} | "
            f"{row['spatial_mean_single_record_support']:.0f} | "
            f"{100.0 * row['spatial_mean_fisher_at_gap']:.2f}% | "
            f"{100.0 * row['spatial_mean_uniform_random_at_gap']:.2f}% | "
            f"{100.0 * row['spatial_mean_fair_random_at_gap']:.2f}% | "
            f"{row['spatial_mean_gap_pp_vs_uniform']:+.2f} | "
            f"{row['spatial_mean_gap_pp_vs_fair']:+.2f} | "
            f"{'yes' if row['all_subjects_keep_half_lossless'] else 'no'} |"
        )

    lines.extend(
        [
            "",
            "## Lossless keep=0.5",
            "",
            "Constant bits outside the active support never change Hamming distance. "
            "Whenever `active_support ≤ D/2`, any mask that retains all active bits "
            "(including Fisher @ keep=0.5) matches full-width accuracy.",
            "",
            "## Fair random baseline",
            "",
            "`mask_random_from_support()` samples keep-bits **only from positions that "
            "vary** on encoded windows. Uniform random over all D bits wastes draws on "
            "frozen bits; the fair baseline removes that artifact.",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_active_bit_ablation.py --quick",
            "python3 python_ref/run_active_bit_ablation.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checkpoint(out_dir: Path, meta: dict, per_cell: List[dict]) -> None:
    path = out_dir / "active_bit_ablation_results.partial.json"
    path.write_text(
        json.dumps({"meta": meta, "per_cell": per_cell}, indent=2),
        encoding="utf-8",
    )


def parse_seeds(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 5 active-bit ablation")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--seeds", type=str, default=None, help="item_mem seeds, e.g. 1,7,21,42")
    p.add_argument("--subjects", type=int, nargs="*", default=None)
    p.add_argument("--d-list", type=int, nargs="*", default=None)
    p.add_argument("--max-windows", type=int, default=None)
    p.add_argument("--max-train-windows", type=int, default=None)
    p.add_argument("--random-seeds", type=int, nargs="*", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    sweep_cfg = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    cnt_w = int(sweep_cfg["cnt_w"])
    gap_keep_ratio = float(sweep_cfg["gap_keep_ratio"])

    if args.quick:
        q = sweep_cfg["quick"]
        item_mem_seeds = (
            parse_seeds(args.seeds) if args.seeds else q.get("item_mem_seeds") or sweep_cfg["item_mem_seeds"]
        )
        subjects = args.subjects or q.get("subjects") or sweep_cfg["subjects"]
        d_list = args.d_list or q.get("D_list") or sweep_cfg["D_list"]
        max_windows = q.get("max_test_windows_per_subject")
        max_train_windows = q.get("max_train_windows_per_subject")
        random_seeds = args.random_seeds or q.get("random_seeds") or sweep_cfg["random_seeds"]
        jobs = [(int(s), int(d), int(subj)) for s in item_mem_seeds for d in d_list for subj in subjects]
    else:
        item_mem_seeds = parse_seeds(args.seeds) if args.seeds else sweep_cfg["item_mem_seeds"]
        subjects = args.subjects or sweep_cfg["subjects"]
        d_list = args.d_list or sweep_cfg["D_list"]
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
        jobs = [(int(s), int(d), int(subj)) for s in item_mem_seeds for d in d_list for subj in subjects]
        extra = sweep_cfg.get("D_sweep_extra") or {}
        if extra and args.d_list is None and args.seeds is None and args.subjects is None:
            for s in extra.get("item_mem_seeds", []):
                for d in extra.get("D_list", []):
                    for subj in extra.get("subjects", subjects):
                        jobs.append((int(s), int(d), int(subj)))
        # de-dupe while preserving order
        seen = set()
        uniq = []
        for job in jobs:
            if job not in seen:
                seen.add(job)
                uniq.append(job)
        jobs = uniq

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    d_list_meta = sorted({d for _, d, _ in jobs})
    seed_list_meta = sorted({s for s, _, _ in jobs})

    print("=" * 70)
    print("Issue 5 — active-bit ablation (hdc_ref / RTL encoder)")
    print(f"  protocol={protocol_id}  CNT_W={cnt_w}")
    print(f"  item_mem_seeds={seed_list_meta}  D_list={d_list_meta}")
    print(f"  gap @ keep={gap_keep_ratio}  random_seeds={list(random_seeds)}")
    print(f"  n_jobs={len(jobs)}  subjects_in_jobs={sorted({s for _, _, s in jobs})}")
    print(f"  max_train={max_train_windows or 'all'}  max_test={max_windows or 'all'}")
    print("=" * 70)

    t0 = time.time()
    per_cell: List[dict] = []
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 5,
        "engine": sweep_cfg.get("engine", "hdc_ref"),
        "protocol": protocol_id,
        "emg_config": str(args.emg_config.relative_to(REPO)),
        "subjects": sorted({s for _, _, s in jobs}),
        "D_list": d_list_meta,
        "cnt_w": cnt_w,
        "item_mem_seeds": seed_list_meta,
        "gap_keep_ratio": gap_keep_ratio,
        "n_keep_at_gap_D1024": int(round(1024 * gap_keep_ratio)),
        "random_seeds": list(random_seeds),
        "max_train_windows_per_subject": max_train_windows,
        "max_test_windows_per_subject": max_windows,
        "n_jobs": len(jobs),
    }

    for item_mem_seed, D, subject in jobs:
        print(f"\n== item_mem_seed={item_mem_seed}  D={D}  subject={subject} ==", flush=True)
        row = eval_cell(
            subject,
            int(D),
            cnt_w,
            int(item_mem_seed),
            gap_keep_ratio,
            random_seeds,
            seed,
            train_frac,
            max_windows,
            max_train_windows,
            split_kw,
        )
        per_cell.append(row)
        meta["elapsed_s"] = round(time.time() - t0, 1)
        _write_checkpoint(args.out_dir, meta, per_cell)

    summary = aggregate(per_cell)
    meta["elapsed_s"] = round(time.time() - t0, 1)
    meta["summary"] = summary

    out_json = args.out_dir / "active_bit_ablation_results.json"
    out_json.write_text(
        json.dumps({"meta": meta, "per_cell": per_cell}, indent=2),
        encoding="utf-8",
    )
    write_csv(args.out_dir / "active_bit_ablation_summary.csv", summary)
    write_readme(args.out_dir / "README.md", meta, summary, per_cell)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    for row in summary:
        print(
            f"  seed={row['item_mem_seed']:>2} D={row['D']}: "
            f"active={row['spatial_mean_active_pooled']:.0f} "
            f"record={row['spatial_mean_single_record_support']:.0f} "
            f"gap_uni={row['spatial_mean_gap_pp_vs_uniform']:+.2f}pp "
            f"gap_fair={row['spatial_mean_gap_pp_vs_fair']:+.2f}pp "
            f"half_lossless={row['all_subjects_keep_half_lossless']}"
        )
    print(f"Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
