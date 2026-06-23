#!/usr/bin/env python3
"""
Export EMG test windows for on-board replay (Phase 3, v2).

v2: full TEST split, all config subjects (concatenated in subject order).
Levels packed for RTL (hdc_ref grid); accuracy/export ref from --engine.

Engines:
  hdc_ref     — RTL-matched encoder + Hamming AM (item mem seed 42, default for board)
  stage_b_bsc — Stage B BSC spatial model (frozen ~90.30% baseline @ D=1024)

Train/test split: frozen protocol P-may2026 (emg_baseline.json):
  train: first 25% of each class, shuffled (rng = seed + 100)
  test:  full per-subject sequence (spatial, stride 1)

Usage (from repo root):
  python3 scripts/export_emg_board_vectors.py
  python3 scripts/export_emg_board_vectors.py --engine stage_b_bsc --summary-only
  python3 scripts/export_emg_board_vectors.py --max-windows 2000   # dev subset

Requires:
  git clone https://github.com/abbas-rahimi/HDC-EMG python_ref/HDC-EMG
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import scipy.io as sio

REPO = Path(__file__).resolve().parents[1]
PYREF = REPO / "python_ref"
sys.path.insert(0, str(PYREF))
sys.path.insert(0, str(PYREF / "repro"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bundle_majority_unlimited,
    bits_to_hex_lines,
)
from stage_b_bsc import (  # noqa: E402
    build_bind_tables,
    gen_train_data as stage_b_gen_train_data,
    init_item_memories,
    predict as stage_b_predict,
    quantize as stage_b_quantize,
    records_for,
    train_prototypes as stage_b_train_prototypes,
)

DATASET = PYREF / "HDC-EMG" / "dataset.mat"
DEFAULT_CONFIG = PYREF / "config" / "emg_baseline.json"
DEFAULT_OUT = REPO / "sw" / "emg_board_vectors.h"

EMG_MAXL = 21
EMG_PRECISION = 1
N_CLASS = 5


def load_config(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_dataset() -> None:
    if DATASET.is_file():
        return
    raise FileNotFoundError(
        "EMG dataset not found.\n"
        f"  expected: {DATASET}\n"
        "  clone with:\n"
        "    cd python_ref && git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG"
    )


def quantize_envelope(data: np.ndarray) -> np.ndarray:
    return np.clip((data * EMG_PRECISION).astype(np.int64), 0, EMG_MAXL)


def level21_to_grid(sample_q4: np.ndarray, cfg: HDCConfig) -> np.ndarray:
    grid = np.zeros((cfg.n_channels, cfg.n_features), dtype=np.int32)
    for c in range(cfg.n_channels):
        lvl21 = int(np.clip(int(sample_q4[c]), 0, EMG_MAXL))
        lvl16 = int(round(lvl21 * (cfg.n_levels - 1) / EMG_MAXL))
        lvl16 = int(np.clip(lvl16, 0, cfg.n_levels - 1))
        for f in range(cfg.n_features):
            grid[c, f] = lvl16
    return grid


def pack_levels_u32(grid: np.ndarray, cfg: HDCConfig) -> Tuple[int, int, int]:
    n_ch = cfg.n_channels
    n_ft = cfg.n_features
    level_w = max(1, int(math.ceil(math.log2(cfg.n_levels))))
    packed = 0
    for c in range(n_ch):
        for f in range(n_ft):
            p = c * n_ft + f
            packed |= (int(grid[c, f]) & ((1 << level_w) - 1)) << (level_w * p)
    return (
        packed & 0xFFFFFFFF,
        (packed >> 32) & 0xFFFFFFFF,
        (packed >> 64) & 0xFFFF,
    )


def split_train_test(
    q_all: np.ndarray,
    labels: np.ndarray,
    train_frac: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng_train = np.random.default_rng(seed + 100)
    train_q, train_labels = stage_b_gen_train_data(q_all, labels, train_frac, rng_train)
    return train_q, train_labels, q_all, labels


def train_prototypes_hdc_ref(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    train_q: np.ndarray,
    train_labels: np.ndarray,
) -> np.ndarray:
    protos = np.zeros((N_CLASS, cfg.D), dtype=np.uint8)
    for k in range(1, N_CLASS + 1):
        idx = np.where(train_labels == k)[0]
        if idx.size == 0:
            continue
        windows = [
            engine.encode_emg_window(level21_to_grid(train_q[i], cfg), mem)
            for i in idx
        ]
        protos[k - 1] = bundle_majority_unlimited(windows, cfg)
    return protos


def evaluate_subject_hdc_ref(
    subject: int,
    cfg: HDCConfig,
    seed: int,
    train_frac: float,
    item_mem_seed: int,
    max_test_windows: int | None = None,
) -> dict:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)

    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed
    )

    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q = test_q[:max_test_windows]
        test_labels = test_labels[:max_test_windows]

    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    mask = np.ones(cfg.D, dtype=np.uint8)
    protos = train_prototypes_hdc_ref(engine, mem, cfg, train_q, train_labels)
    protos8 = np.zeros((8, cfg.D), dtype=np.uint8)
    protos8[:N_CLASS] = protos

    levels0: List[int] = []
    levels1: List[int] = []
    levels2: List[int] = []
    emg_labels: List[int] = []
    expect: List[int] = []
    preds: List[int] = []

    for i in range(test_q.shape[0]):
        if i > 0 and i % 10000 == 0:
            print(f"    subject {subject}: {i}/{test_q.shape[0]} test windows", flush=True)
        grid = level21_to_grid(test_q[i], cfg)
        query = engine.encode_emg_window(grid, mem)
        res = engine.classify(query, protos, mask=mask)
        l0, l1, l2 = pack_levels_u32(grid, cfg)
        levels0.append(l0)
        levels1.append(l1)
        levels2.append(l2)
        raw_label = int(test_labels[i])
        emg_labels.append(raw_label)
        expect.append(((res.class_id << 16) | (res.distance & 0xFFFF)))
        preds.append(res.class_id)

    gt = np.array([int(l) - 1 for l in test_labels], dtype=np.int32)
    pred_arr = np.array(preds, dtype=np.int32)
    valid = (gt >= 0) & (gt < N_CLASS)
    accuracy = float(np.mean(pred_arr[valid] == gt[valid])) if valid.any() else 0.0

    return {
        "subject": subject,
        "n_windows": int(test_q.shape[0]),
        "n_train": int(train_q.shape[0]),
        "accuracy": accuracy,
        "levels0": levels0,
        "levels1": levels1,
        "levels2": levels2,
        "labels": emg_labels,
        "expect": expect,
        "protos": protos8,
        "mask": mask,
    }


def evaluate_subject_stage_b(
    subject: int,
    D: int,
    seed: int,
    train_frac: float,
    cfg: HDCConfig,
    max_test_windows: int | None = None,
) -> dict:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)

    rng = np.random.default_rng(seed)
    CiM, iM = init_item_memories(D, rng)
    T = build_bind_tables(CiM, iM)

    q_all = stage_b_quantize(data)
    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed
    )

    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q = test_q[:max_test_windows]
        test_labels = test_labels[:max_test_windows]

    rec_tr = records_for(T, train_q)
    rec_te = records_for(T, test_q)
    protos = stage_b_train_prototypes(rec_tr, train_labels, D)
    pred = stage_b_predict(rec_te, protos)

    levels0: List[int] = []
    levels1: List[int] = []
    levels2: List[int] = []
    emg_labels: List[int] = []
    expect: List[int] = []

    for i in range(test_q.shape[0]):
        grid = level21_to_grid(test_q[i], cfg)
        l0, l1, l2 = pack_levels_u32(grid, cfg)
        levels0.append(l0)
        levels1.append(l1)
        levels2.append(l2)
        raw_label = int(test_labels[i])
        emg_labels.append(raw_label)
        class_id = int(pred[i]) - 1
        if class_id < 0:
            class_id = 0
        expect.append((class_id << 16))

    gt = test_labels.astype(np.int64)
    valid = (gt >= 1) & (gt <= N_CLASS)
    accuracy = float(np.mean(pred[valid] == gt[valid])) if valid.any() else 0.0

    # Stage B protos are rows 1..5 in (6, D); store as 8-class layout for board loader.
    protos8 = np.zeros((8, D), dtype=np.uint8)
    protos8[:N_CLASS] = protos[1 : N_CLASS + 1]

    return {
        "subject": subject,
        "n_windows": int(test_q.shape[0]),
        "n_train": int(train_q.shape[0]),
        "accuracy": accuracy,
        "levels0": levels0,
        "levels1": levels1,
        "levels2": levels2,
        "labels": emg_labels,
        "expect": expect,
        "protos": protos8,
        "mask": np.ones(D, dtype=np.uint8),
    }


def merge_subjects(subject_results: Sequence[dict]) -> dict:
    levels0: List[int] = []
    levels1: List[int] = []
    levels2: List[int] = []
    labels: List[int] = []
    expect: List[int] = []
    window_subject: List[int] = []
    subj_windows: List[int] = []
    protos_stack: List[np.ndarray] = []

    total_correct = 0
    total_valid = 0

    for r in subject_results:
        n = r["n_windows"]
        subj_windows.append(n)
        protos_stack.append(r["protos"])

        for i in range(n):
            raw_label = int(r["labels"][i])
            gt_idx = raw_label - 1
            exp = int(r["expect"][i])
            pred_idx = (exp >> 16) & 0xFFFF
            if 0 <= gt_idx < N_CLASS:
                total_valid += 1
                if pred_idx == gt_idx:
                    total_correct += 1

            levels0.append(r["levels0"][i])
            levels1.append(r["levels1"][i])
            levels2.append(r["levels2"][i])
            labels.append(raw_label)
            expect.append(exp)
            window_subject.append(int(r["subject"]))

    accuracy = (total_correct / total_valid) if total_valid else 0.0
    mask = subject_results[0]["mask"]
    protos_all = np.stack(protos_stack, axis=0)

    return {
        "n_windows": len(levels0),
        "accuracy": accuracy,
        "levels0": levels0,
        "levels1": levels1,
        "levels2": levels2,
        "labels": labels,
        "expect": expect,
        "window_subject": window_subject,
        "subj_windows": subj_windows,
        "protos": protos_all,
        "mask": mask,
        "subjects": [int(r["subject"]) for r in subject_results],
    }


def fmt_u64_array(name: str, protos: np.ndarray, cfg: HDCConfig) -> str:
    """protos shape (n_subjects, EMG_N_CLASS, D) flattened for C."""
    lines: List[str] = []
    n_subjects = protos.shape[0]
    for s in range(n_subjects):
        for k in range(8):
            row = protos[s, k]
            for hex_line in bits_to_hex_lines(row, cfg.words, cfg.bits_per_word):
                lines.append(f"0x{int(hex_line, 16):016x}ULL")
    body = ",\n    ".join(lines)
    return (
        f"static const u64 {name}[EMG_N_SUBJECTS * EMG_N_CLASS * EMG_WORDS64] = {{\n"
        f"    {body}\n}};"
    )


def fmt_mask64(name: str, mask: np.ndarray, cfg: HDCConfig) -> str:
    lines = [
        f"0x{int(h, 16):016x}ULL"
        for h in bits_to_hex_lines(mask, cfg.words, cfg.bits_per_word)
    ]
    body = ",\n    ".join(lines)
    return f"static const u64 {name}[EMG_WORDS64] = {{\n    {body}\n}};"


def write_header(
    path: Path,
    cfg: HDCConfig,
    cfg_json: dict,
    engine: str,
    item_mem_seed: int,
    result: dict,
) -> None:
    n = result["n_windows"]
    acc_x1000 = int(round(result["accuracy"] * 100000))
    subjects = result["subjects"]
    protocol = cfg_json["protocol"]["id"]
    seed = int(cfg_json["seed"])
    split = "test"
    train_frac = float(cfg_json["protocol"]["train_fraction"])

    u32_list = lambda vals: ",\n    ".join(f"0x{v:08x}U" for v in vals)
    u8_list = lambda vals: ",\n    ".join(str(v) for v in vals)

    engine_define = (
        "#define EMG_ENGINE_STAGE_B          1U"
        if engine == "stage_b_bsc"
        else "#define EMG_ENGINE_HDC_REF          1U"
    )

    subj_win_str = ", ".join(str(w) for w in result["subj_windows"])
    subj_list_str = ", ".join(str(s) for s in subjects)

    comment_block = [
        "/* EMG board vectors v2 — auto-generated, do not edit.",
        f" * engine={engine}",
        f" * protocol={protocol}  split={split}  seed={seed}  train_frac={train_frac}",
        f" * item_mem_seed={item_mem_seed}  D={cfg.D}",
        f" * subjects=[{subj_list_str}]  windows_per_subject=[{subj_win_str}]",
        f" * export_ref_accuracy={acc_x1000 / 1000:.2f}%",
        " */",
    ]

    lines = comment_block + [
        "#ifndef EMG_BOARD_VECTORS_H",
        "#define EMG_BOARD_VECTORS_H",
        "",
        '#include "xil_types.h"',
        "",
        "#define EMG_EXPORT_VERSION              2U",
        engine_define,
        f"#define EMG_BOARD_WINDOWS               {n}U",
        f"#define EMG_N_SUBJECTS                  {len(subjects)}U",
        f"#define EMG_N_CLASS                     8U",
        f"#define EMG_WORDS64                     {cfg.words}U",
        f"#define EMG_SEED                        {seed}U",
        f"#define EMG_ITEM_MEM_SEED               {item_mem_seed}U",
        f"#define EMG_EXPORT_REF_ACCURACY_X1000   {acc_x1000}U",
        "",
        f"static const u32 emg_subj_windows[EMG_N_SUBJECTS] = {{ {subj_win_str} }};",
        "",
        fmt_u64_array("emg_proto64", result["protos"], cfg),
        "",
        fmt_mask64("emg_mask64", result["mask"], cfg),
        "",
        f"static const u32 emg_levels0[EMG_BOARD_WINDOWS] = {{\n    {u32_list(result['levels0'])}\n}};",
        "",
        f"static const u32 emg_levels1[EMG_BOARD_WINDOWS] = {{\n    {u32_list(result['levels1'])}\n}};",
        "",
        f"static const u32 emg_levels2[EMG_BOARD_WINDOWS] = {{\n    {u32_list(result['levels2'])}\n}};",
        "",
        f"static const u8 emg_labels[EMG_BOARD_WINDOWS] = {{\n    {u8_list(result['labels'])}\n}};",
        "",
        f"static const u8 emg_window_subject[EMG_BOARD_WINDOWS] = {{\n    {u8_list(result['window_subject'])}\n}};",
        "",
        f"static const u32 emg_expect[EMG_BOARD_WINDOWS] = {{\n    {u32_list(result['expect'])}\n}};",
        "",
        "#endif",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_summary(
    subjects: Sequence[int],
    cfg: HDCConfig,
    cfg_json: dict,
    engine: str,
    item_mem_seed: int,
    max_windows: int | None,
) -> None:
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    D = int(cfg_json["project_baseline_model"]["D"])

    print(f"{'subj':>4}  {'windows':>8}  {'train':>8}  {'accuracy':>10}")
    print("-" * 36)
    results = []
    remaining = max_windows
    for s in subjects:
        cap = None
        if remaining is not None:
            if remaining <= 0:
                break
            cap = remaining
        if engine == "stage_b_bsc":
            r = evaluate_subject_stage_b(s, D, seed, train_frac, cfg, cap)
        else:
            r = evaluate_subject_hdc_ref(s, cfg, seed, train_frac, item_mem_seed, cap)
        results.append(r)
        if remaining is not None:
            remaining -= r["n_windows"]
        print(
            f"{s:4d}  {r['n_windows']:8d}  {r['n_train']:8d}  "
            f"{r['accuracy'] * 100:9.2f}%"
        )

    merged = merge_subjects(results)
    print("-" * 36)
    print(
        f"mean accuracy ({engine}, exported set): "
        f"{merged['accuracy'] * 100:.2f}%  (N={merged['n_windows']})"
    )
    if engine == "stage_b_bsc":
        print("Frozen May 2026 baseline (Stage B spatial @ D=1024): ~90.30%")
    else:
        print("Use --engine stage_b_bsc to compare against frozen 90.30% baseline.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export EMG board vectors v2 (Phase 3)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--engine",
        choices=("hdc_ref", "stage_b_bsc"),
        default="hdc_ref",
        help="Engine for export ref accuracy/expect (default: hdc_ref, RTL-matched)",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="Dev cap: first N windows after subject-order concat (default: all test)",
    )
    parser.add_argument(
        "--subjects",
        type=int,
        nargs="+",
        default=None,
        help="Subject ids (default: all from config)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print per-subject accuracy only (no header write)",
    )
    parser.add_argument(
        "--item-mem-seed",
        type=int,
        default=42,
        help="hdc_ref item memory seed (must match FPGA cosim_core .mem, default 42)",
    )
    args = parser.parse_args()

    require_dataset()
    cfg_json = load_config(args.config)
    subjects = args.subjects if args.subjects else cfg_json["dataset"]["subjects"]
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    D = int(cfg_json["project_baseline_model"]["D"])
    cfg = HDCConfig(D=D, seed=args.item_mem_seed)

    if args.summary_only:
        run_summary(subjects, cfg, cfg_json, args.engine, args.item_mem_seed, args.max_windows)
        return 0

    print(f"Exporting TEST split, subjects={subjects}, engine={args.engine} ...")
    subject_results = []
    remaining = args.max_windows
    for s in subjects:
        cap = None
        if remaining is not None:
            if remaining <= 0:
                break
            cap = remaining
        print(f"  subject {s}...", flush=True)
        if args.engine == "stage_b_bsc":
            subject_results.append(
                evaluate_subject_stage_b(s, D, seed, train_frac, cfg, cap)
            )
        else:
            subject_results.append(
                evaluate_subject_hdc_ref(
                    s, cfg, seed, train_frac, args.item_mem_seed, cap
                )
            )
        if remaining is not None:
            remaining -= subject_results[-1]["n_windows"]

    merged = merge_subjects(subject_results)
    write_header(args.out, cfg, cfg_json, args.engine, args.item_mem_seed, merged)

    print(f"Wrote {args.out}")
    print(f"  version:     v2")
    print(f"  engine:      {args.engine}")
    print(f"  subjects:    {subjects}")
    print(f"  windows:     {merged['n_windows']} total")
    print(f"  per-subject: {merged['subj_windows']}")
    print(f"  export ref:  {merged['accuracy'] * 100:.2f}%")
    print(f"  protocol:    {cfg_json['protocol']['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
