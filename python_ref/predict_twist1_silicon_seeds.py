#!/usr/bin/env python3
"""Predict Twist-1 silicon random-mask accuracy for seeds 0–9 (issue #26).

Board EMG replay scores against the same labels and protos as this script.
Seed 0 validated board == export ref (Δ0.00 pp); we treat export ref as the
silicon predictor for remaining seeds until JTAG replay completes.

Mask: **pooled** random iso-density @ keep=0.125 — matches patch_emg_anchor.py
and run_twist1_board.sh (not per-subject Twist-1 Python sweep masks).

Usage:
  python3 python_ref/predict_twist1_silicon_seeds.py
  python3 python_ref/predict_twist1_silicon_seeds.py --seeds 1 2 3 --quick
  python3 python_ref/predict_twist1_silicon_seeds.py --out-dir results/protocol_v2/twist1_silicon
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "python_ref"))

from hdc_ref import HDCConfig, HDCEngine, ItemMemory, bits_from_u64_words  # noqa: E402
from scripts.export_emg_board_vectors import (  # noqa: E402
    DATASET,
    N_CLASS,
    level21_to_grid,
    quantize_envelope,
    split_kwargs_from_config,
    split_train_test,
    train_prototypes_hdc_ref,
)

DEFAULT_OUT = REPO / "results" / "protocol_v2" / "twist1_silicon"
DEFAULT_HDR = REPO / "sw" / "emg_board_vectors_hdc2.h"
DEFAULT_BIN = REPO / "sw" / "emg_board_vectors.bin"
DEFAULT_V2_CFG = REPO / "python_ref" / "config" / "emg_baseline_v2.json"

KEEP_RATIO = 0.125
N_WINDOWS = 493_512
INFORMED_BOARD_ACC = 72.84  # anchor C measured (protocol_v2/anchors/anchor_C)
INFORMED_EXPORT_REF = 72.85
SEED0_BOARD_ACC = 62.51
SEED0_EXPORT_REF = 62.51


def build_random_mask(cfg: HDCConfig, keep_ratio: float, random_seed: int) -> np.ndarray:
    from hdc_ref import mask_from_scores

    rng = np.random.default_rng(random_seed)
    mask = mask_from_scores(
        np.zeros(cfg.D, dtype=np.float64),
        keep_ratio,
        rng=rng,
        informed=False,
    )
    return mask.astype(np.uint8)


def load_cohort_from_dataset(
    cfg_json: dict,
    cfg: HDCConfig,
    cache_path: Path | None = None,
    max_encode_windows: int | None = None,
) -> tuple[list[int], list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """Per-subject test hypervectors, labels, protos — HDC-2 board cohort."""
    if not DATASET.is_file():
        raise SystemExit(
            f"missing {DATASET}\n"
            "  clone: git clone https://github.com/abbas-rahimi/HDC-EMG python_ref/HDC-EMG"
        )

    if cache_path and cache_path.is_file():
        print(f"Loading cached cohort from {cache_path} ...", flush=True)
        data = np.load(cache_path, allow_pickle=True)
        subjects = list(data["subjects"])
        all_test_hvs = list(data["test_hvs"])
        all_test_labels = list(data["test_labels"])
        all_protos = list(data["protos"])
        return subjects, all_test_hvs, all_test_labels, all_protos

    import scipy.io as sio

    subjects = cfg_json["dataset"]["subjects"]
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(cfg_json)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    mat = sio.loadmat(str(DATASET))

    all_test_hvs: list[np.ndarray] = []
    all_test_labels: list[np.ndarray] = []
    all_protos: list[np.ndarray] = []
    encoded_total = 0

    for subject in subjects:
        data = mat[f"COMPLETE_{subject}"].astype(np.float64)
        labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
        q_all = quantize_envelope(data)
        train_q, train_labels, test_q, test_labels = split_train_test(
            q_all, labels, train_frac, seed, **split_kw
        )
        print(
            f"  subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}",
            flush=True,
        )
        protos = train_prototypes_hdc_ref(engine, mem, cfg, train_q, train_labels)

        n_test = test_q.shape[0]
        if max_encode_windows is not None:
            remain = max_encode_windows - encoded_total
            if remain <= 0:
                all_protos.append(protos)
                all_test_hvs.append(np.empty((0, cfg.D), dtype=np.uint8))
                all_test_labels.append(np.empty(0, dtype=np.int64))
                continue
            n_test = min(n_test, remain)

        test_hvs = np.empty((n_test, cfg.D), dtype=np.uint8)
        for i in range(n_test):
            if i > 0 and i % 25000 == 0:
                print(f"    subject {subject}: encoded {i}/{n_test}", flush=True)
            test_hvs[i] = engine.encode_emg_window(level21_to_grid(test_q[i], cfg), mem)
        encoded_total += n_test

        all_protos.append(protos)
        all_test_hvs.append(test_hvs)
        all_test_labels.append(test_labels[:n_test])

    if cache_path and max_encode_windows is None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            cache_path,
            subjects=np.array(subjects),
            test_hvs=np.array(all_test_hvs, dtype=object),
            test_labels=np.array(all_test_labels, dtype=object),
            protos=np.array(all_protos, dtype=object),
        )
        print(f"Cached cohort -> {cache_path}", flush=True)

    return subjects, all_test_hvs, all_test_labels, all_protos


def accuracy_pooled_mask(
    all_test_hvs: Sequence[np.ndarray],
    all_test_labels: Sequence[np.ndarray],
    all_protos: Sequence[np.ndarray],
    mask: np.ndarray,
    max_windows: int | None,
) -> tuple[float, int, int]:
    engine = HDCEngine(HDCConfig(D=mask.shape[0]))
    total_correct = 0
    total_valid = 0
    remaining = max_windows

    for test_hvs, test_labels, protos in zip(all_test_hvs, all_test_labels, all_protos):
        n = test_hvs.shape[0]
        if remaining is not None:
            n = min(n, remaining)
            if n <= 0:
                break
        for i in range(n):
            pred = engine.classify(test_hvs[i], protos, mask=mask).class_id
            gt = int(test_labels[i]) - 1
            if 0 <= gt < N_CLASS:
                total_valid += 1
                if int(pred) == gt:
                    total_correct += 1
        if remaining is not None:
            remaining -= n

    acc = (total_correct / total_valid) if total_valid else 0.0
    return acc, total_correct, total_valid


def parse_board_acc(path: Path) -> float | None:
    if not path.is_file():
        return None
    m = re.search(r"accuracy=([\d.]+)%", path.read_text(encoding="utf-8", errors="replace"))
    return float(m.group(1)) if m else None


def load_subj_windows(slim_header: Path) -> List[int]:
    text = slim_header.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"emg_subj_windows\[EMG_N_SUBJECTS\] = \{([^}]+)\}", text)
    if not m:
        raise SystemExit(f"could not parse emg_subj_windows in {slim_header}")
    return [int(x.strip()) for x in m.group(1).split(",")]


def predict_seed_from_dataset(
    seed: int,
    cfg: HDCConfig,
    all_test_hvs: Sequence[np.ndarray],
    all_test_labels: Sequence[np.ndarray],
    all_protos: Sequence[np.ndarray],
    max_windows: int | None,
) -> Dict[str, Any]:
    t0 = time.time()
    mask = build_random_mask(cfg, KEEP_RATIO, seed)
    acc, correct, n_eval = accuracy_pooled_mask(
        all_test_hvs, all_test_labels, all_protos, mask, max_windows
    )
    predicted_board = acc * 100.0
    return {
        "seed": seed,
        "keep_ratio": KEEP_RATIO,
        "mask_mode": "random_pooled",
        "n_keep": int(mask.sum()),
        "n_windows": n_eval,
        "n_correct": correct,
        "export_ref_accuracy_pct": round(acc * 100, 4),
        "predicted_board_accuracy_pct": round(predicted_board, 4),
        "gap_vs_informed_board_pp": round(INFORMED_BOARD_ACC - predicted_board, 4),
        "prediction_method": "export_ref_calibrated",
        "calibration_note": "Seed 0 board matched export ref (Δ0.00 pp); same path assumed.",
        "elapsed_s": round(time.time() - t0, 1),
        "mask_density": round(float(mask.mean()), 6),
        "data_source": "dataset.mat",
    }


def predict_seed_from_bin(
    seed: int,
    cfg: HDCConfig,
    protos_all: np.ndarray,
    subj_windows: Sequence[int],
    l0: np.ndarray,
    l1: np.ndarray,
    l2: np.ndarray,
    labels: np.ndarray,
    max_windows: int | None,
) -> Dict[str, Any]:
    from scripts.patch_emg_anchor import recompute_accuracy_with_mask

    t0 = time.time()
    mask = build_random_mask(cfg, KEEP_RATIO, seed)
    acc = recompute_accuracy_with_mask(
        cfg, protos_all, subj_windows, l0, l1, l2, labels, mask, max_windows
    )
    n_eval = min(len(labels), max_windows) if max_windows else len(labels)
    predicted_board = acc * 100.0
    gap_pp = INFORMED_BOARD_ACC - predicted_board
    return {
        "seed": seed,
        "keep_ratio": KEEP_RATIO,
        "mask_mode": "random_pooled",
        "n_keep": int(mask.sum()),
        "n_windows": n_eval,
        "export_ref_accuracy_pct": round(acc * 100, 4),
        "predicted_board_accuracy_pct": round(predicted_board, 4),
        "gap_vs_informed_board_pp": round(gap_pp, 4),
        "prediction_method": "export_ref_calibrated",
        "calibration_note": "Seed 0 board matched export ref (Δ0.00 pp); same path assumed.",
        "elapsed_s": round(time.time() - t0, 1),
        "mask_density": round(float(mask.mean()), 6),
        "data_source": "emg_board_vectors.bin",
    }


def write_seed_artifact(out_dir: Path, seed: int, result: Dict[str, Any]) -> None:
    sdir = out_dir / f"random_seed_{seed}"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "prediction.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if result.get("board_measured"):
        return
    status_lines = [
        f"Twist 1 random seed {seed} — export-ref silicon prediction",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Export ref ({result['n_windows']} windows): {result['export_ref_accuracy_pct']:.2f}%",
        f"Predicted board accuracy: {result['predicted_board_accuracy_pct']:.2f}%",
        f"Gap vs informed anchor C ({INFORMED_BOARD_ACC:.2f}%): "
        f"{result['gap_vs_informed_board_pp']:+.2f} pp",
        "",
        "Method: pooled random mask @ keep=0.125 (patch_emg_anchor.py path).",
        "Board replay: pending — run scripts/run_silicon_random_seeds.sh --board",
    ]
    (sdir / "patch_status.txt").write_text("\n".join(status_lines) + "\n", encoding="utf-8")


def merge_board_if_present(out_dir: Path, seed: int, result: Dict[str, Any]) -> Dict[str, Any]:
    board_path = out_dir / f"random_seed_{seed}" / "board_emg_replay.txt"
    board_acc = parse_board_acc(board_path)
    if board_acc is not None:
        result["board_accuracy_pct"] = board_acc
        result["board_vs_export_delta_pp"] = round(board_acc - result["export_ref_accuracy_pct"], 4)
        result["board_measured"] = True
        result["gap_vs_informed_board_pp"] = round(INFORMED_BOARD_ACC - board_acc, 4)
    else:
        result["board_measured"] = False
    return result


def summarize(out_dir: Path, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    measured = [r for r in rows if r.get("board_measured")]
    predicted = [r["predicted_board_accuracy_pct"] for r in rows]
    gaps_pred = [r["gap_vs_informed_board_pp"] for r in rows]

    summary: Dict[str, Any] = {
        "issue": 26,
        "keep_ratio": KEEP_RATIO,
        "informed_anchor_C_board_pct": INFORMED_BOARD_ACC,
        "informed_anchor_C_export_ref_pct": INFORMED_EXPORT_REF,
        "n_windows": rows[0]["n_windows"] if rows else N_WINDOWS,
        "prediction_method": "export_ref_calibrated",
        "calibration": {
            "seed_0_board_pct": SEED0_BOARD_ACC,
            "seed_0_export_ref_pct": SEED0_EXPORT_REF,
            "board_export_delta_pp": 0.0,
        },
        "seeds": rows,
        "aggregate_predicted": {
            "mean_accuracy_pct": round(float(np.mean(predicted)), 4),
            "std_accuracy_pct": round(float(np.std(predicted, ddof=1)) if len(predicted) > 1 else 0.0, 4),
            "mean_gap_pp": round(float(np.mean(gaps_pred)), 4),
            "std_gap_pp": round(float(np.std(gaps_pred, ddof=1)) if len(gaps_pred) > 1 else 0.0, 4),
            "min_gap_pp": round(float(min(gaps_pred)), 4),
            "max_gap_pp": round(float(max(gaps_pred)), 4),
        },
    }
    if measured:
        board_gaps = [r["gap_vs_informed_board_pp"] for r in measured]
        summary["aggregate_measured"] = {
            "n_seeds": len(measured),
            "mean_gap_pp": round(float(np.mean(board_gaps)), 4),
            "std_gap_pp": round(
                float(np.std(board_gaps, ddof=1)) if len(board_gaps) > 1 else 0.0, 4
            ),
        }
    return summary


def write_readme(out_dir: Path, summary: Dict[str, Any]) -> None:
    agg = summary["aggregate_predicted"]
    lines = [
        "# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)",
        "",
        f"**Windows:** {summary['n_windows']:,} (HDC-2 pooled cohort)",
        f"**Informed (anchor C):** {summary['informed_anchor_C_board_pct']:.2f}% board",
        "",
        "## Predicted random-mask distribution (seeds 0–9)",
        "",
        f"| Stat | Predicted board acc | Gap vs informed (pp) |",
        f"|------|---------------------|----------------------|",
        f"| Mean ± std | **{agg['mean_accuracy_pct']:.2f}% ± {agg['std_accuracy_pct']:.2f}** | "
        f"**{agg['mean_gap_pp']:+.2f} ± {agg['std_gap_pp']:.2f}** |",
        f"| Range (gap) | — | {agg['min_gap_pp']:+.2f} … {agg['max_gap_pp']:+.2f} |",
        "",
        "| Seed | Export ref | Predicted board | Gap (pp) | Board measured |",
        "|------|------------|-----------------|----------|----------------|",
    ]
    for r in summary["seeds"]:
        meas = "✅" if r.get("board_measured") else "⏳"
        lines.append(
            f"| {r['seed']} | {r['export_ref_accuracy_pct']:.2f}% | "
            f"{r['predicted_board_accuracy_pct']:.2f}% | "
            f"{r['gap_vs_informed_board_pp']:+.2f} | {meas} |"
        )
    lines.extend(
        [
            "",
            "**Method:** `python_ref/predict_twist1_silicon_seeds.py` — pooled random mask,",
            "same export path as `patch_emg_anchor.py`. Seed 0 board validated Δ0.00 pp.",
            "",
            "## Board replay (when ZedBoard available)",
            "",
            "```bash",
            "bash scripts/run_silicon_random_seeds.sh --board --seeds 1-9",
            "```",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Predict Twist-1 silicon random-mask seeds")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--header", type=Path, default=DEFAULT_HDR)
    ap.add_argument("--slim-header", type=Path, default=REPO / "sw" / "emg_board_vectors.h")
    ap.add_argument("--bin", type=Path, default=DEFAULT_BIN)
    ap.add_argument("--config", type=Path, default=DEFAULT_V2_CFG)
    ap.add_argument("--max-windows", type=int, default=None, help="dev cap (quick test)")
    ap.add_argument(
        "--from-dataset",
        action="store_true",
        help="encode from dataset.mat (default when bin/header missing)",
    )
    ap.add_argument(
        "--skip-cache",
        action="store_true",
        help="force re-encode cohort (ignore cohort_cache.npz)",
    )
    args = ap.parse_args()

    cfg_json = json.loads(args.config.read_text(encoding="utf-8"))
    cfg = HDCConfig(D=1024, seed=int(cfg_json.get("item_mem_seed", 42)))

    use_dataset = args.from_dataset or not args.bin.is_file()
    all_test_hvs = all_test_labels = all_protos = None
    protos_all = subj_windows = l0 = l1 = l2 = labels = None

    if use_dataset:
        cache = args.out_dir / "cohort_cache.npz"
        if args.skip_cache and cache.is_file():
            cache.unlink()
        print("Loading HDC-2 cohort from dataset.mat ...", flush=True)
        _, all_test_hvs, all_test_labels, all_protos = load_cohort_from_dataset(
            cfg_json,
            cfg,
            cache_path=cache if args.max_windows is None else None,
            max_encode_windows=args.max_windows,
        )
    else:
        from scripts.patch_emg_anchor import load_protos_from_header
        from scripts.regenerate_emg_protos import load_levels_labels_bin, parse_defines, parse_subjects

        if not args.slim_header.is_file():
            raise SystemExit(f"missing {args.slim_header}")
        defs = parse_defines(args.slim_header)
        subjects = parse_subjects(defs, args.slim_header)
        subj_windows = load_subj_windows(args.slim_header)
        header_for_protos = args.header if args.header.is_file() else args.slim_header
        protos_all = load_protos_from_header(header_for_protos, cfg, len(subjects))
        n = defs["EMG_BOARD_WINDOWS"]
        print(f"Loading {n} windows from {args.bin} ...", flush=True)
        l0, l1, l2, labels = load_levels_labels_bin(args.bin, n)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Copy seed 0 board measurement from phase3 if present
    phase3_seed0 = REPO / "results" / "phase3" / "twist1_silicon" / "random_seed_0"
    if phase3_seed0.is_dir():
        import shutil

        dst0 = args.out_dir / "random_seed_0"
        dst0.mkdir(parents=True, exist_ok=True)
        for name in ("board_emg_replay.txt", "patch_status.txt"):
            src = phase3_seed0 / name
            if src.is_file() and not (dst0 / name).is_file():
                shutil.copy2(src, dst0 / name)

    rows: List[Dict[str, Any]] = []

    for seed in args.seeds:
        print(f"\n=== Seed {seed} ===", flush=True)
        if use_dataset:
            result = predict_seed_from_dataset(
                seed, cfg, all_test_hvs, all_test_labels, all_protos, args.max_windows
            )
        else:
            result = predict_seed_from_bin(
                seed, cfg, protos_all, subj_windows, l0, l1, l2, labels, args.max_windows
            )
        result = merge_board_if_present(args.out_dir, seed, result)
        write_seed_artifact(args.out_dir, seed, result)
        rows.append(result)
        print(
            f"  export_ref={result['export_ref_accuracy_pct']:.2f}%  "
            f"predicted_board={result['predicted_board_accuracy_pct']:.2f}%  "
            f"gap={result['gap_vs_informed_board_pp']:+.2f} pp  "
            f"({result['elapsed_s']}s)",
            flush=True,
        )

    summary = summarize(args.out_dir, rows)
    summary_path = args.out_dir / "seed_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_readme(args.out_dir, summary)
    print(f"\nWrote {summary_path}")
    print(
        f"Predicted gap: {summary['aggregate_predicted']['mean_gap_pp']:+.2f} "
        f"± {summary['aggregate_predicted']['std_gap_pp']:.2f} pp "
        f"(n={len(rows)} seeds)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
