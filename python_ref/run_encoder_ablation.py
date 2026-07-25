#!/usr/bin/env python3
"""
Issue #6 - Path B encoder ablation (Stage B BSC -> RTL Eq. 3.1).

Measure spatial-mean accuracy under a controlled ladder that isolates
item-memory seed, level count, binding structure, and bind count.
Protocol HDC-2 (disjoint 75% test) is used for all deployment-relevant rows;
one literature Stage-B row keeps the classic full-recording test for parity.

Usage (from repo root):
  python3 python_ref/run_encoder_ablation.py --quick
  python3 python_ref/run_encoder_ablation.py

Outputs:
  results/protocol_v2/encoder_ablation/encoder_ablation_results.json
  results/protocol_v2/encoder_ablation/encoder_ablation_summary.csv
  results/protocol_v2/encoder_ablation/README.md
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
sys.path.insert(0, str(HERE / "repro"))
sys.path.insert(0, str(REPO / "scripts"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bundle_majority,
    bundle_majority_unlimited,
)
from stage_b_bsc import (  # noqa: E402
    MAXL,
    build_bind_tables,
    gen_random_bits,
    predict as stage_b_predict,
    records_for,
    train_prototypes as stage_b_train_prototypes,
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

DEFAULT_CFG = HERE / "config" / "encoder_ablation.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "encoder_ablation"

STEP_META: Dict[str, dict] = {
    "stage_b_literature_fulltest": {
        "label": "Stage B BSC (literature protocol)",
        "change": "Full-recording test (HDC-1-style); Rahimi parity reference",
        "test_set": "full_recording",
        "family": "stage_b",
    },
    "stage_b_hdc2": {
        "label": "Stage B BSC @ HDC-2",
        "change": "Same encoder; disjoint 75% test (Protocol HDC-2)",
        "test_set": "disjoint",
        "family": "stage_b",
        "item_seed": "protocol",
        "n_levels": 22,
    },
    "stage_b_hdc2_seed42": {
        "label": "Stage B + item-mem seed 42",
        "change": "Replace protocol seed with RTL item_mem_seed=42",
        "test_set": "disjoint",
        "family": "stage_b",
        "item_seed": 42,
        "n_levels": 22,
    },
    "stage_b_hdc2_16levels": {
        "label": "Stage B + 16-level CiM",
        "change": "Map envelope 21->16 levels (RTL grid depth)",
        "test_set": "disjoint",
        "family": "stage_b",
        "item_seed": 42,
        "n_levels": 16,
    },
    "rtl_4bind": {
        "label": "RTL item mem + 4 binds",
        "change": "Eq. 3.1 bind (ch⊕val⊕ρ(feat0)); majority of 4 channels",
        "test_set": "disjoint",
        "family": "rtl",
        "n_binds": 4,
    },
    "rtl_20bind": {
        "label": "RTL encoder (20 binds)",
        "change": "Full Eq. 3.1 grid: 4×5 feature slots, deployed path",
        "test_set": "disjoint",
        "family": "rtl",
        "n_binds": 20,
    },
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hdc_cfg(D: int, item_mem_seed: int) -> HDCConfig:
    return HDCConfig(D=D, words=D // 64, bits_per_word=64, seed=item_mem_seed)


def cap_windows_random(
    q: np.ndarray,
    labels: np.ndarray,
    n_max: int,
    *,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray]:
    if q.shape[0] <= n_max:
        return q, labels
    idx = rng.choice(q.shape[0], size=int(n_max), replace=False)
    idx.sort()
    return q[idx], labels[idx]


def map_levels_21_to_16(q: np.ndarray, n_levels: int = 16) -> np.ndarray:
    """Map Stage-B envelope levels [0,21] -> [0, n_levels-1]."""
    out = np.round(q.astype(np.float64) * (n_levels - 1) / MAXL).astype(np.int64)
    return np.clip(out, 0, n_levels - 1)


def init_item_memories_nlevels(D: int, rng: np.random.Generator, n_levels: int):
    """Stage-B continuous CiM with ``n_levels`` rows (levels 0..n_levels-1)."""
    if n_levels < 2:
        raise ValueError("n_levels must be >= 2")
    iM = np.stack([gen_random_bits(D, rng) for _ in range(4)]).astype(np.uint8)
    current = gen_random_bits(D, rng)
    rand_idx = rng.permutation(D)
    # Match Stage-B spacing: flip ~D/(2*(n_levels-1)) bits per step
    sp = max(1, D // 2 // (n_levels - 1))
    CiM = np.empty((n_levels, D), dtype=np.uint8)
    for i in range(n_levels):
        CiM[i] = current
        if i + 1 < n_levels:
            start = i * sp
            end = min(D, (i + 1) * sp + 1)
            current = current.copy()
            current[rand_idx[start:end]] ^= 1
    return CiM, iM


def accuracy_stage_b(
    train_q: np.ndarray,
    train_labels: np.ndarray,
    test_q: np.ndarray,
    test_labels: np.ndarray,
    D: int,
    item_seed: int,
    n_levels: int,
) -> Tuple[float, int, int]:
    q_tr, q_te = train_q, test_q
    if n_levels != (MAXL + 1):
        q_tr = map_levels_21_to_16(train_q, n_levels)
        q_te = map_levels_21_to_16(test_q, n_levels)
    rng = np.random.default_rng(item_seed)
    CiM, iM = init_item_memories_nlevels(D, rng, n_levels)
    T = build_bind_tables(CiM, iM)
    rec_tr = records_for(T, q_tr)
    rec_te = records_for(T, q_te)
    protos = stage_b_train_prototypes(rec_tr, train_labels, D)
    pred = stage_b_predict(rec_te, protos)
    gt = test_labels.astype(np.int64)
    valid = (gt >= 1) & (gt <= N_CLASS)
    n = int(valid.sum())
    correct = int(np.sum(pred[valid] == gt[valid])) if n else 0
    return (correct / n if n else 0.0), correct, n


def encode_rtl_windows(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    q: np.ndarray,
    *,
    n_binds: int,
    cnt_w: int,
    progress: str = "",
) -> np.ndarray:
    n = q.shape[0]
    out = np.zeros((n, cfg.D), dtype=np.uint8)
    step = max(1, n // 20)
    for i in range(n):
        if progress and i > 0 and i % step == 0:
            print(f"      encode {progress}: {i}/{n}", flush=True)
        grid = level21_to_grid(q[i], cfg)
        if n_binds == 20:
            out[i] = engine.encode_emg_window(grid, mem, cnt_bits=cnt_w)
        elif n_binds == 4:
            parts = [
                engine.encode_record_pair(c, 0, int(grid[c, 0]), mem)
                for c in range(cfg.n_channels)
            ]
            out[i] = bundle_majority(parts, cfg, cnt_bits=cnt_w)
        else:
            raise ValueError(f"unsupported n_binds={n_binds}")
    return out


def accuracy_rtl(
    train_q: np.ndarray,
    train_labels: np.ndarray,
    test_q: np.ndarray,
    test_labels: np.ndarray,
    cfg: HDCConfig,
    cnt_w: int,
    n_binds: int,
    progress_prefix: str,
) -> Tuple[float, int, int]:
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    train_hvs = encode_rtl_windows(
        engine, mem, cfg, train_q, n_binds=n_binds, cnt_w=cnt_w, progress=f"{progress_prefix}/train"
    )
    test_hvs = encode_rtl_windows(
        engine, mem, cfg, test_q, n_binds=n_binds, cnt_w=cnt_w, progress=f"{progress_prefix}/test"
    )
    protos = np.zeros((N_CLASS, cfg.D), dtype=np.uint8)
    for k in range(1, N_CLASS + 1):
        idx = np.where(train_labels == k)[0]
        if idx.size == 0:
            continue
        protos[k - 1] = bundle_majority_unlimited([train_hvs[i] for i in idx], cfg)

    m = np.ones((1, cfg.D), dtype=np.uint8)
    dists = np.stack(
        [((test_hvs ^ protos[k]) & m).sum(axis=1) for k in range(N_CLASS)], axis=1
    )
    pred = dists.argmin(axis=1).astype(np.int32)
    gt = test_labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    n = int(gt.shape[0])
    return (correct / n if n else 0.0), correct, n


def eval_step_subject(
    step: str,
    subject: int,
    D: int,
    cnt_w: int,
    protocol_seed: int,
    item_mem_seed_rtl: int,
    train_frac: float,
    split_kw: dict,
    max_train: Optional[int],
    max_test: Optional[int],
) -> dict:
    meta = STEP_META[step]
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)

    test_set = meta["test_set"]
    boundary_gap = int(split_kw.get("boundary_gap", 0))
    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all,
        labels,
        train_frac,
        protocol_seed,
        test_set=test_set,
        boundary_gap=boundary_gap,
    )
    cap_rng = np.random.default_rng(protocol_seed + 1000 * subject + (hash(step) % 997))
    if max_train is not None and train_q.shape[0] > max_train:
        train_q, train_labels = cap_windows_random(train_q, train_labels, max_train, rng=cap_rng)
    if max_test is not None and test_q.shape[0] > max_test:
        test_q, test_labels = cap_windows_random(test_q, test_labels, max_test, rng=cap_rng)

    print(
        f"    {step} s{subject}: train={train_q.shape[0]} test={test_q.shape[0]} "
        f"test_set={test_set}",
        flush=True,
    )

    if meta["family"] == "stage_b":
        if step == "stage_b_literature_fulltest":
            item_seed = protocol_seed
            n_levels = MAXL + 1
        else:
            raw_seed = meta.get("item_seed", "protocol")
            item_seed = protocol_seed if raw_seed == "protocol" else int(raw_seed)
            n_levels = int(meta.get("n_levels", MAXL + 1))
        acc, correct, n_test = accuracy_stage_b(
            train_q, train_labels, test_q, test_labels, D, item_seed, n_levels
        )
    else:
        cfg = hdc_cfg(D, item_mem_seed_rtl)
        acc, correct, n_test = accuracy_rtl(
            train_q,
            train_labels,
            test_q,
            test_labels,
            cfg,
            cnt_w,
            int(meta["n_binds"]),
            progress_prefix=f"{step}/s{subject}",
        )

    return {
        "step": step,
        "subject": subject,
        "accuracy": acc,
        "correct": correct,
        "n_test": n_test,
        "n_train": int(train_q.shape[0]),
        "test_set": test_set,
        "label": meta["label"],
        "change": meta["change"],
    }


def aggregate(per_cell: List[dict], steps: Sequence[str]) -> List[dict]:
    out = []
    for step in steps:
        rows = [r for r in per_cell if r["step"] == step]
        if not rows:
            continue
        accs = [r["accuracy"] for r in rows]
        out.append(
            {
                "step": step,
                "label": STEP_META[step]["label"],
                "change": STEP_META[step]["change"],
                "test_set": STEP_META[step]["test_set"],
                "n_subjects": len(rows),
                "spatial_mean_accuracy": float(np.mean(accs)),
                "spatial_std_accuracy": float(np.std(accs)) if len(accs) > 1 else 0.0,
                "per_subject_accuracy": {str(r["subject"]): r["accuracy"] for r in rows},
            }
        )
    return out


def write_csv(path: Path, summary: List[dict]) -> None:
    fields = [
        "step",
        "label",
        "change",
        "test_set",
        "n_subjects",
        "spatial_mean_accuracy",
        "spatial_std_accuracy",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in summary:
            w.writerow({k: row[k] for k in fields})


def write_readme(path: Path, meta: dict, summary: List[dict]) -> None:
    lines = [
        "# Issue 6 - Path B encoder ablation (Stage B -> RTL)",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · D={meta['D']} · subjects={meta['subjects']}",
        "",
        "Path A (BSC in PL) is **out of scope**. This table explains the ~17 pp gap",
        "between the literature BSC reference and the deployed RTL encoder.",
        "",
        "## Spatial mean",
        "",
        "| Step | Configuration | Test set | Acc | Δ vs prev (pp) |",
        "|------|---------------|----------|-----|----------------|",
    ]
    prev = None
    for row in summary:
        acc = 100.0 * row["spatial_mean_accuracy"]
        if prev is None:
            dlt = "-"
        else:
            dlt = f"{acc - 100.0 * prev:+.2f}"
        lines.append(
            f"| `{row['step']}` | {row['label']} | {row['test_set']} | "
            f"**{acc:.2f}%** | {dlt} |"
        )
        prev = row["spatial_mean_accuracy"]

    lines.extend(
        [
            "",
            "## What moves the needle",
            "",
            "- **Protocol** (full test -> HDC-2 disjoint) can shift Stage B absolute accuracy.",
            "- **Item-memory seed** (1 -> 42) is usually a small effect.",
            "- **21->16 levels** is usually a small effect.",
            "- **Binding + 4->20 binds** (Stage B records -> Eq. 3.1 grid) is the main drop.",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_encoder_ablation.py --quick",
            "python3 python_ref/run_encoder_ablation.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 6 Path B encoder ablation")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--subjects", type=int, nargs="*", default=None)
    p.add_argument("--max-windows", type=int, default=None)
    p.add_argument("--max-train-windows", type=int, default=None)
    p.add_argument("--steps", type=str, nargs="*", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()
    sweep_cfg = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    D = int(sweep_cfg["D"])
    cnt_w = int(sweep_cfg["cnt_w"])
    item_mem_seed_rtl = int(sweep_cfg["item_mem_seed_rtl"])
    protocol_seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    if args.quick:
        q = sweep_cfg["quick"]
        subjects = args.subjects or q.get("subjects") or sweep_cfg["subjects"]
        steps = args.steps or q.get("steps") or sweep_cfg["steps"]
        max_test = q.get("max_test_windows_per_subject")
        max_train = q.get("max_train_windows_per_subject")
    else:
        subjects = args.subjects or sweep_cfg["subjects"]
        steps = args.steps or sweep_cfg["steps"]
        max_test = (
            args.max_windows
            if args.max_windows is not None
            else sweep_cfg.get("max_test_windows_per_subject")
        )
        max_train = (
            args.max_train_windows
            if args.max_train_windows is not None
            else sweep_cfg.get("max_train_windows_per_subject")
        )

    for s in steps:
        if s not in STEP_META:
            raise SystemExit(f"unknown step: {s}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 70)
    print("Issue 6 - Path B encoder ablation (Stage B -> RTL)")
    print(f"  protocol={protocol_id}  D={D}  subjects={subjects}")
    print(f"  steps={list(steps)}")
    print(f"  max_train={max_train or 'all'}  max_test={max_test or 'all'}")
    print("=" * 70)

    t0 = time.time()
    per_cell: List[dict] = []
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 6,
        "path": "B",
        "protocol": protocol_id,
        "emg_config": str(args.emg_config.relative_to(REPO)),
        "subjects": list(subjects),
        "D": D,
        "cnt_w": cnt_w,
        "item_mem_seed_rtl": item_mem_seed_rtl,
        "protocol_seed": protocol_seed,
        "steps": list(steps),
        "max_train_windows_per_subject": max_train,
        "max_test_windows_per_subject": max_test,
    }

    for step in steps:
        print(f"\n== {step}: {STEP_META[step]['label']} ==", flush=True)
        for subject in subjects:
            row = eval_step_subject(
                step,
                int(subject),
                D,
                cnt_w,
                protocol_seed,
                item_mem_seed_rtl,
                train_frac,
                split_kw,
                max_train,
                max_test,
            )
            per_cell.append(row)
            meta["elapsed_s"] = round(time.time() - t0, 1)
            (args.out_dir / "encoder_ablation_results.partial.json").write_text(
                json.dumps({"meta": meta, "per_cell": per_cell}, indent=2),
                encoding="utf-8",
            )

    summary = aggregate(per_cell, steps)
    meta["elapsed_s"] = round(time.time() - t0, 1)
    meta["summary"] = summary

    # Deltas along the HDC-2 ladder (skip literature fulltest for delta chain note)
    hdc2_rows = [r for r in summary if r["test_set"] == "disjoint"]
    if len(hdc2_rows) >= 2:
        meta["hdc2_total_drop_pp"] = round(
            100.0
            * (hdc2_rows[0]["spatial_mean_accuracy"] - hdc2_rows[-1]["spatial_mean_accuracy"]),
            2,
        )

    out_json = args.out_dir / "encoder_ablation_results.json"
    out_json.write_text(
        json.dumps({"meta": meta, "per_cell": per_cell}, indent=2), encoding="utf-8"
    )
    write_csv(args.out_dir / "encoder_ablation_summary.csv", summary)
    write_readme(args.out_dir / "README.md", meta, summary)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    for row in summary:
        print(
            f"  {row['step']:32s} {100.0 * row['spatial_mean_accuracy']:6.2f}%  "
            f"({row['label']})"
        )
    print(f"Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
