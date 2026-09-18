#!/usr/bin/env python3
"""
Issue #40 — native D=128 / D=256 encode-and-classify vs K=128 Fisher gather @ D=1024.

Native width: item memory and bind at D (not a mask on a D=1024 hypervector).
Compare to Option E: Fisher top-128 at D=1024, then baked gather (narrow datapath).

Usage (from repo root):
  python3 python_ref/run_native_d_sweep.py --quick
  python3 python_ref/run_native_d_sweep.py
  python3 python_ref/run_native_d_sweep.py --engine hdc_ref

Outputs:
  results/protocol_v2/native_d_sweep/native_d_sweep_results.json
  results/protocol_v2/native_d_sweep/native_d_sweep_summary.csv
  results/protocol_v2/native_d_sweep/README.md
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
    gather_narrow_bits,
    mask_from_scores,
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
from stage_b_engine import StageBConfig, StageBEngine, split_subject_hdc2  # noqa: E402

DEFAULT_CFG = HERE / "config" / "native_d_sweep.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "native_d_sweep"


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


def classify_full_width(
    test_hvs: np.ndarray,
    test_labels: np.ndarray,
    protos: np.ndarray,
) -> Tuple[float, int, int, np.ndarray]:
    total = int(test_labels.shape[0])
    if total == 0:
        return 0.0, 0, 0, np.zeros(0, dtype=np.int32)
    q = np.asarray(test_hvs, dtype=np.uint8)
    p = np.asarray(protos, dtype=np.uint8)
    dists = np.stack([(q ^ p[k]).sum(axis=1) for k in range(p.shape[0])], axis=1)
    pred = dists.argmin(axis=1).astype(np.int32)
    gt = test_labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    return correct / total, correct, total, pred


def classify_masked(
    test_hvs: np.ndarray,
    test_labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> Tuple[float, int, int, np.ndarray]:
    m = (np.asarray(mask, dtype=np.uint8) & 1).reshape(1, -1)
    q = np.asarray(test_hvs, dtype=np.uint8)
    p = np.asarray(protos, dtype=np.uint8)
    dists = np.stack([((q ^ p[k]) & m).sum(axis=1) for k in range(p.shape[0])], axis=1)
    pred = dists.argmin(axis=1).astype(np.int32)
    gt = test_labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    total = int(test_labels.shape[0])
    return correct / total, correct, total, pred


def classify_gather(
    test_hvs: np.ndarray,
    test_labels: np.ndarray,
    protos: np.ndarray,
    sel: np.ndarray,
) -> Tuple[float, int, int, np.ndarray]:
    sel = np.asarray(sel, dtype=np.int64)
    q = np.asarray(test_hvs, dtype=np.uint8)
    p = np.asarray(protos, dtype=np.uint8)
    qn = q[:, sel]
    pn = p[:, sel]
    dists = np.stack([(qn ^ pn[k]).sum(axis=1) for k in range(pn.shape[0])], axis=1)
    pred = dists.argmin(axis=1).astype(np.int32)
    gt = test_labels.astype(np.int32) - 1
    correct = int(np.sum(pred == gt))
    total = int(test_labels.shape[0])
    return correct / total, correct, total, pred


def pred_agreement(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0:
        return 1.0
    return float(np.mean(a == b))


def load_subject_windows_hdc2(
    subject: int,
    seed: int,
    train_frac: float,
    split_kw: dict,
    max_train: Optional[int],
    max_test: Optional[int],
    cap_rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)
    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed, **split_kw
    )
    if max_train is not None and train_q.shape[0] > max_train:
        train_q, train_labels = cap_windows_random(
            train_q, train_labels, max_train, rng=cap_rng
        )
    if max_test is not None and test_q.shape[0] > max_test:
        test_q, test_labels = cap_windows_random(test_q, test_labels, max_test, rng=cap_rng)
    return train_q, train_labels, test_q, test_labels


def eval_subject_hdc_ref(
    subject: int,
    *,
    native_D: Sequence[int],
    item_mem_seed: int,
    cnt_w: int,
    gather_keep_ratio: float,
    gather_k_bits: int,
    seed: int,
    train_frac: float,
    split_kw: dict,
    max_train: Optional[int],
    max_test: Optional[int],
) -> dict:
    cap_rng = np.random.default_rng(seed + 1000 * subject + item_mem_seed)
    train_q, train_labels, test_q, test_labels = load_subject_windows_hdc2(
        subject, seed, train_frac, split_kw, max_train, max_test, cap_rng
    )
    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}",
        flush=True,
    )

    modes: Dict[str, dict] = {}
    d1024_train_hvs = None
    d1024_test_hvs = None
    d1024_protos = None

    for D in native_D:
        cfg = hdc_cfg_for_d(D, item_mem_seed)
        mem = ItemMemory(cfg)
        engine = HDCEngine(cfg)
        train_hvs = encode_queries_hdc(
            engine, mem, cfg, train_q, cnt_w, f"s{subject}/D{D}/train"
        )
        test_hvs = encode_queries_hdc(engine, mem, cfg, test_q, cnt_w, f"s{subject}/D{D}/test")
        protos = train_prototypes_from_hvs(train_hvs, train_labels, cfg)
        acc, correct, n_test, _ = classify_full_width(test_hvs, test_labels, protos)
        key = f"native_D{D}_full"
        modes[key] = {
            "mode": key,
            "D": D,
            "accuracy": acc,
            "correct": correct,
            "n_test": n_test,
        }
        if D == 1024:
            d1024_train_hvs = train_hvs
            d1024_test_hvs = test_hvs
            d1024_protos = protos

    if d1024_train_hvs is None or d1024_test_hvs is None or d1024_protos is None:
        raise RuntimeError("native_D must include 1024 for gather comparison")

    fisher_scores = per_bit_fisher_scores(
        d1024_train_hvs, train_labels.astype(np.int32)
    )
    fisher_mask = mask_from_scores(
        fisher_scores, gather_keep_ratio, informed=True
    ).astype(np.uint8)
    sel = np.flatnonzero(fisher_mask)
    if sel.size != gather_k_bits:
        fisher_mask = mask_topk_from_scores(fisher_scores, gather_k_bits)
        sel = np.flatnonzero(fisher_mask)

    acc_m, correct_m, n_test, pred_m = classify_masked(
        d1024_test_hvs, test_labels, d1024_protos, fisher_mask
    )
    acc_g, correct_g, _, pred_g = classify_gather(
        d1024_test_hvs, test_labels, d1024_protos, sel
    )
    modes["d1024_fisher_k128_masked"] = {
        "mode": "d1024_fisher_k128_masked",
        "D": 1024,
        "k_bits": int(fisher_mask.sum()),
        "accuracy": acc_m,
        "correct": correct_m,
        "n_test": n_test,
    }
    modes["d1024_option_e_k128_gather"] = {
        "mode": "d1024_option_e_k128_gather",
        "D": 1024,
        "k_bits": int(sel.size),
        "accuracy": acc_g,
        "correct": correct_g,
        "n_test": n_test,
        "pred_agreement_vs_masked": pred_agreement(pred_g, pred_m),
    }

    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "n_train": int(train_q.shape[0]),
        "modes": modes,
    }


def eval_subject_stage_b(
    subject: int,
    *,
    native_D: Sequence[int],
    item_mem_seed: int,
    gather_keep_ratio: float,
    gather_k_bits: int,
    seed: int,
    train_frac: float,
    split_kw: dict,
    max_train: Optional[int],
    max_test: Optional[int],
) -> dict:
    cap_rng = np.random.default_rng(seed + 2000 * subject + item_mem_seed)
    train_q, train_labels, test_q, test_labels = split_subject_hdc2(
        subject, seed=seed, train_frac=train_frac, split_kw=split_kw
    )
    if max_train is not None and train_q.shape[0] > max_train:
        train_q, train_labels = cap_windows_random(
            train_q, train_labels, max_train, rng=cap_rng
        )
    if max_test is not None and test_q.shape[0] > max_test:
        test_q, test_labels = cap_windows_random(test_q, test_labels, max_test, rng=cap_rng)

    print(
        f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}",
        flush=True,
    )

    modes: Dict[str, dict] = {}
    d1024_train_hvs = None
    d1024_test_hvs = None
    d1024_protos = None

    for D in native_D:
        engine = StageBEngine(StageBConfig(D=D, item_mem_seed=item_mem_seed))
        train_hvs = engine.encode_quantized(train_q)
        test_hvs = engine.encode_quantized(test_q)
        protos = engine.train_prototypes(train_hvs, train_labels)
        acc, correct, n_test, _ = classify_full_width(test_hvs, test_labels, protos)
        modes[f"native_D{D}_full"] = {
            "mode": f"native_D{D}_full",
            "D": D,
            "accuracy": acc,
            "correct": correct,
            "n_test": n_test,
        }
        if D == 1024:
            d1024_train_hvs = train_hvs
            d1024_test_hvs = test_hvs
            d1024_protos = protos

    fisher_scores = per_bit_fisher_scores(
        d1024_train_hvs, train_labels.astype(np.int32)
    )
    fisher_mask = mask_from_scores(
        fisher_scores, gather_keep_ratio, informed=True
    ).astype(np.uint8)
    sel = np.flatnonzero(fisher_mask)
    if sel.size != gather_k_bits:
        fisher_mask = mask_topk_from_scores(fisher_scores, gather_k_bits)
        sel = np.flatnonzero(fisher_mask)

    acc_m, correct_m, n_test, pred_m = classify_masked(
        d1024_test_hvs, test_labels, d1024_protos, fisher_mask
    )
    acc_g, correct_g, _, pred_g = classify_gather(
        d1024_test_hvs, test_labels, d1024_protos, sel
    )
    modes["d1024_fisher_k128_masked"] = {
        "mode": "d1024_fisher_k128_masked",
        "D": 1024,
        "k_bits": int(fisher_mask.sum()),
        "accuracy": acc_m,
        "correct": correct_m,
        "n_test": n_test,
    }
    modes["d1024_option_e_k128_gather"] = {
        "mode": "d1024_option_e_k128_gather",
        "D": 1024,
        "k_bits": int(sel.size),
        "accuracy": acc_g,
        "correct": correct_g,
        "n_test": n_test,
        "pred_agreement_vs_masked": pred_agreement(pred_g, pred_m),
    }

    return {
        "subject": subject,
        "item_mem_seed": item_mem_seed,
        "n_train": int(train_q.shape[0]),
        "modes": modes,
    }


def aggregate(per_subject: List[dict], mode_keys: Sequence[str]) -> dict:
    summary: Dict[str, dict] = {}
    for key in mode_keys:
        accs = [row["modes"][key]["accuracy"] for row in per_subject]
        correct = sum(row["modes"][key]["correct"] for row in per_subject)
        n_test = sum(row["modes"][key]["n_test"] for row in per_subject)
        entry = {
            "spatial_mean_accuracy": float(np.mean(accs)),
            "spatial_std_accuracy": float(np.std(accs)) if len(accs) > 1 else 0.0,
            "pooled_accuracy": correct / n_test if n_test else 0.0,
            "pooled_correct": correct,
            "pooled_n_test": n_test,
            "per_subject_accuracy": {
                str(row["subject"]): row["modes"][key]["accuracy"] for row in per_subject
            },
        }
        if key == "d1024_option_e_k128_gather":
            entry["spatial_mean_pred_agreement_vs_masked"] = float(
                np.mean(
                    [
                        row["modes"][key]["pred_agreement_vs_masked"]
                        for row in per_subject
                    ]
                )
            )
        summary[key] = entry
    return summary


def write_csv(path: Path, engine: str, summary: dict, mode_keys: Sequence[str]) -> None:
    fields = [
        "engine",
        "mode",
        "spatial_mean_accuracy",
        "pooled_accuracy",
        "spatial_std_accuracy",
    ]
    rows = []
    for key in mode_keys:
        s = summary[key]
        rows.append(
            {
                "engine": engine,
                "mode": key,
                "spatial_mean_accuracy": s["spatial_mean_accuracy"],
                "pooled_accuracy": s["pooled_accuracy"],
                "spatial_std_accuracy": s["spatial_std_accuracy"],
            }
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_readme(path: Path, meta: dict, summaries: Dict[str, dict]) -> None:
    lines = [
        "# Issue 40 — native D vs K=128 gather (HDC-2)",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · CNT_W={meta['cnt_w']} · item_mem_seed={meta['item_mem_seed']}",
        f"Subjects: {meta['subjects']}",
        f"Test cap: {meta.get('max_test_windows_per_subject') or 'all'} windows/subject",
        "",
        "## Spatial mean (S1–S5)",
        "",
        "| Engine | Mode | Spatial mean | Pooled |",
        "|--------|------|--------------|--------|",
    ]
    for eng, summ in summaries.items():
        for key, s in summ.items():
            lines.append(
                f"| {eng} | {key} | {100*s['spatial_mean_accuracy']:.2f}% | "
                f"{100*s['pooled_accuracy']:.2f}% |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- **native_D***: encode and classify entirely at hypervector width D.",
            "- **d1024_fisher_k128_masked**: Fisher free-choice mask @ keep=0.125 on D=1024 queries.",
            "- **d1024_option_e_k128_gather**: same decisions as masked path (gather bit-exact).",
            "- Compare native D=256 to Hook A D=256 @ CNT_W=6 (`protocol_v2/hook_a/`).",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_native_d_sweep.py --quick",
            "python3 python_ref/run_native_d_sweep.py",
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 40 native D sweep")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--engine", choices=("hdc_ref", "stage_b", "all"), default="all")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    sweep = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    if args.quick:
        q = sweep["quick"]
        engines = q.get("engines") or sweep["engines"]
        subjects = q.get("subjects") or sweep["subjects"]
        max_test = q.get("max_test_windows_per_subject")
        max_train = q.get("max_train_windows_per_subject")
    else:
        engines = sweep["engines"]
        subjects = sweep["subjects"]
        max_test = sweep.get("max_test_windows_per_subject")
        max_train = sweep.get("max_train_windows_per_subject")

    if args.engine != "all":
        engines = [args.engine]

    native_D = [int(x) for x in sweep["native_D"]]
    if 1024 not in native_D:
        raise SystemExit("native_D must include 1024")

    cnt_w = int(sweep["cnt_w"])
    gather_keep_ratio = float(sweep["gather_keep_ratio"])
    gather_k_bits = int(sweep["gather_k_bits"])
    hdc_seed = int(sweep["item_mem_seed"])
    stage_b_seed = int(sweep.get("stage_b_item_mem_seed", 1))

    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    protocol_id = emg_cfg.get("protocol", {}).get("id", "HDC-2")

    mode_keys = [
        "native_D128_full",
        "native_D256_full",
        "native_D1024_full",
        "d1024_fisher_k128_masked",
        "d1024_option_e_k128_gather",
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 40,
        "protocol": protocol_id,
        "subjects": list(subjects),
        "native_D": native_D,
        "cnt_w": cnt_w,
        "gather_keep_ratio": gather_keep_ratio,
        "gather_k_bits": gather_k_bits,
        "item_mem_seed": hdc_seed,
        "stage_b_item_mem_seed": stage_b_seed,
        "max_train_windows_per_subject": max_train,
        "max_test_windows_per_subject": max_test,
    }

    engine_results: Dict[str, dict] = {}
    summaries: Dict[str, dict] = {}
    csv_rows: List[dict] = []

    for eng in engines:
        print(f"\n======== engine {eng} ========", flush=True)
        per_subject: List[dict] = []
        im_seed = hdc_seed if eng == "hdc_ref" else stage_b_seed
        for subject in subjects:
            print(f"\n== {eng} subject {subject} ==", flush=True)
            if eng == "hdc_ref":
                row = eval_subject_hdc_ref(
                    int(subject),
                    native_D=native_D,
                    item_mem_seed=im_seed,
                    cnt_w=cnt_w,
                    gather_keep_ratio=gather_keep_ratio,
                    gather_k_bits=gather_k_bits,
                    seed=seed,
                    train_frac=train_frac,
                    split_kw=split_kw,
                    max_train=max_train,
                    max_test=max_test,
                )
            else:
                row = eval_subject_stage_b(
                    int(subject),
                    native_D=native_D,
                    item_mem_seed=im_seed,
                    gather_keep_ratio=gather_keep_ratio,
                    gather_k_bits=gather_k_bits,
                    seed=seed,
                    train_frac=train_frac,
                    split_kw=split_kw,
                    max_train=max_train,
                    max_test=max_test,
                )
            per_subject.append(row)
            partial = {
                "meta": {**meta, "elapsed_s": round(time.time() - t0, 1)},
                "engines": {eng: {"per_subject": per_subject}},
            }
            (args.out_dir / "native_d_sweep_results.partial.json").write_text(
                json.dumps(partial, indent=2), encoding="utf-8"
            )

        summary = aggregate(per_subject, mode_keys)
        engine_results[eng] = {"per_subject": per_subject, "summary": summary}
        summaries[eng] = summary
        for key in mode_keys:
            csv_rows.append(
                {
                    "engine": eng,
                    "mode": key,
                    **{k: summary[key][k] for k in ("spatial_mean_accuracy", "pooled_accuracy", "spatial_std_accuracy")},
                }
            )

    meta["elapsed_s"] = round(time.time() - t0, 1)
    out_json = args.out_dir / "native_d_sweep_results.json"
    out_json.write_text(
        json.dumps({"meta": meta, "engines": engine_results}, indent=2),
        encoding="utf-8",
    )

    csv_path = args.out_dir / "native_d_sweep_summary.csv"
    fields = ["engine", "mode", "spatial_mean_accuracy", "pooled_accuracy", "spatial_std_accuracy"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)

    write_readme(args.out_dir / "README.md", meta, summaries)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    for eng, summ in summaries.items():
        print(f"  [{eng}]")
        for key in mode_keys:
            s = summ[key]
            print(
                f"    {key:32s} spatial={100*s['spatial_mean_accuracy']:.2f}% "
                f"pooled={100*s['pooled_accuracy']:.2f}%"
            )
    print(f"Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
