#!/usr/bin/env python3
"""Patch Hook A pruning anchor (mask + export ref) without re-exporting window arrays.

Board EMG replay scores against ground-truth labels; only emg_mask64 and
EMG_EXPORT_REF_ACCURACY_X1000 must change between anchors A/B/C. Levels,
protos, and emg_board_vectors.bin stay the same.

Mask (silicon): one **pooled** Fisher-informed mask over all subjects' TRAIN
windows — a single hdc_load_mask_from64 for the full replay.

Anchor A (keep=1.0): Fisher at 100% keep is a **full mask** (all bits set).
Scores are not computed; the result is identical to mask_from_scores(..., 1.0).

Hook A Python sweep (results/hook_a/) uses **per-subject** Fisher masks, then
means accuracy across subjects. At keep=1.0 both paths yield all-ones; at B/C
the bit patterns can differ — state measured board acc vs Hook A 74.15% targets.

Usage:
  python3 scripts/patch_emg_anchor.py --anchor B
  python3 scripts/patch_emg_anchor.py --keep-ratio 0.5 --anchor B
  python3 scripts/patch_emg_anchor.py --anchor C --max-windows 5000   # dev sample
  python3 scripts/patch_emg_anchor.py --keep-ratio 0.125 --mask-mode random --random-seed 0 --label twist1_random_s0
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import List, Sequence

import numpy as np
import scipy.io as sio

REPO = Path(__file__).resolve().parents[1]
PYREF = REPO / "python_ref"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PYREF))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bits_from_u64_words,
    mask_from_scores,
    per_bit_fisher_scores,
)
from scripts.export_emg_board_vectors import (  # noqa: E402
    DATASET,
    N_CLASS,
    fmt_mask64,
    level21_to_grid,
    quantize_envelope,
    split_kwargs_from_config,
    split_train_test,
)
from scripts.regenerate_emg_protos import (  # noqa: E402
    DEFAULT_SLIM,
    load_levels_labels_bin,
    parse_defines,
    parse_subjects,
    unpack_levels_u32,
    update_comment_accuracy,
    update_ref_accuracy,
)

DEFAULT_HDR = REPO / "sw" / "emg_board_vectors_hdc2.h"
DEFAULT_V2_CFG = PYREF / "config" / "emg_baseline_v2.json"

ANCHOR_KEEP = {"A": 1.0, "B": 0.5, "C": 0.125}


def replace_mask_block(text: str, mask_block: str) -> str:
    pat = r"static const u64 emg_mask64\[.*?\] = \{.*?\};"
    if not re.search(pat, text, flags=re.S):
        raise ValueError("emg_mask64 block not found")
    return re.sub(pat, mask_block, text, count=1, flags=re.S)


def replace_golden_mask_block(text: str, mask_block: str) -> str:
    pat = r"static const u64 golden_mask64\[.*?\] = \{.*?\};"
    if not re.search(pat, text, flags=re.S):
        raise ValueError("golden_mask64 block not found")
    return re.sub(pat, mask_block, text, count=1, flags=re.S)


def load_protos_from_header(header: Path, cfg: HDCConfig, n_subjects: int) -> np.ndarray:
    text = header.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"emg_proto64\[.*?\] = \{(.*?)\};", text, flags=re.S)
    if not m:
        raise ValueError(f"emg_proto64 block not found in {header}")
    hex_vals = re.findall(r"0x([0-9a-fA-F]+)ULL", m.group(1))
    want = n_subjects * 8 * cfg.words
    if len(hex_vals) != want:
        raise ValueError(f"expected {want} proto u64 words, got {len(hex_vals)}")
    flat = np.array([int(v, 16) for v in hex_vals], dtype=np.uint64)
    protos_all = np.zeros((n_subjects, 8, cfg.D), dtype=np.uint8)
    for s in range(n_subjects):
        for k in range(8):
            words = flat[(s * 8 + k) * cfg.words : (s * 8 + k + 1) * cfg.words]
            protos_all[s, k] = bits_from_u64_words(words, cfg.D)
    return protos_all


def build_pooled_fisher_mask(
    subjects: Sequence[int],
    cfg: HDCConfig,
    seed: int,
    train_frac: float,
    keep_ratio: float,
    split_kw: dict,
) -> np.ndarray:
    if keep_ratio >= 1.0 - 1e-9:
        # Degenerate Fisher case: 100% keep == all-ones (same as mask_from_scores(..., 1.0)).
        return np.ones(cfg.D, dtype=np.uint8)

    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    train_hvs: List[np.ndarray] = []
    train_labels: List[int] = []

    print("Building pooled Fisher mask from TRAIN windows ...")
    for subject in subjects:
        mat = sio.loadmat(str(DATASET))
        data = mat[f"COMPLETE_{subject}"].astype(np.float64)
        labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
        q_all = quantize_envelope(data)
        train_q, train_y, _, _ = split_train_test(
            q_all, labels, train_frac, seed, **split_kw
        )
        print(f"  subject {subject}: encoding {train_q.shape[0]} train windows", flush=True)
        for i in range(train_q.shape[0]):
            if i > 0 and i % 5000 == 0:
                print(f"    subject {subject}: {i}/{train_q.shape[0]}", flush=True)
            grid = level21_to_grid(train_q[i], cfg)
            train_hvs.append(engine.encode_emg_window(grid, mem))
            train_labels.append(int(train_y[i]))

    scores = per_bit_fisher_scores(np.stack(train_hvs), np.array(train_labels, dtype=np.int32))
    mask = mask_from_scores(scores, keep_ratio, informed=True)
    print(
        f"  keep_ratio={keep_ratio}  density={mask.mean():.4f}  "
        f"n_keep={int(mask.sum())}/{cfg.D}"
    )
    return mask.astype(np.uint8)


def build_random_mask(cfg: HDCConfig, keep_ratio: float, random_seed: int) -> np.ndarray:
    rng = np.random.default_rng(random_seed)
    mask = mask_from_scores(
        np.zeros(cfg.D, dtype=np.float64),
        keep_ratio,
        rng=rng,
        informed=False,
    )
    print(
        f"  random_seed={random_seed}  keep_ratio={keep_ratio}  "
        f"n_keep={int(mask.sum())}/{cfg.D}"
    )
    return mask.astype(np.uint8)


def build_mask(
    subjects: Sequence[int],
    cfg: HDCConfig,
    seed: int,
    train_frac: float,
    keep_ratio: float,
    mask_mode: str,
    random_seed: int,
    split_kw: dict,
) -> np.ndarray:
    if mask_mode == "random":
        return build_random_mask(cfg, keep_ratio, random_seed)
    return build_pooled_fisher_mask(
        subjects, cfg, seed, train_frac, keep_ratio, split_kw
    )


def recompute_accuracy_with_mask(
    cfg: HDCConfig,
    protos_all: np.ndarray,
    subj_windows: Sequence[int],
    l0: np.ndarray,
    l1: np.ndarray,
    l2: np.ndarray,
    labels: np.ndarray,
    mask: np.ndarray,
    max_windows: int | None,
) -> float:
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    n = len(labels)
    if max_windows is not None:
        n = min(n, max_windows)

    offset = 0
    total_correct = 0
    total_valid = 0
    t0 = time.time()

    for subj_idx, subj_n in enumerate(subj_windows):
        if offset >= n:
            break
        run_n = subj_n
        if offset + run_n > n:
            run_n = n - offset
        protos = protos_all[subj_idx, :N_CLASS]

        for i in range(run_n):
            gi = offset + i
            if gi > 0 and gi % 50000 == 0:
                elapsed = time.time() - t0
                print(f"    accuracy pass: {gi}/{n} ({elapsed:.0f}s)", flush=True)
            grid = unpack_levels_u32(int(l0[gi]), int(l1[gi]), int(l2[gi]), cfg)
            query = engine.encode_emg_window(grid, mem)
            pred = engine.classify(query, protos, mask=mask).class_id
            gt = int(labels[gi]) - 1
            if 0 <= gt < N_CLASS:
                total_valid += 1
                if int(pred) == gt:
                    total_correct += 1
        offset += subj_n

    return (total_correct / total_valid) if total_valid else 0.0


def patch_header_comment(text: str, anchor: str, keep_ratio: float, label: str | None = None) -> str:
    tag = f"anchor={anchor}  keep_ratio={keep_ratio}"
    if label:
        tag += f"  label={label}"
    lines = []
    for line in text.splitlines():
        if line.strip() == " */" and "anchor=" not in text:
            lines.append(f" * {tag}")
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r" \* anchor=[^\n]+", f" * {tag}", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch EMG board vectors for Hook A anchor")
    ap.add_argument("--anchor", choices=sorted(ANCHOR_KEEP), help="Hook A anchor id (A/B/C)")
    ap.add_argument("--keep-ratio", type=float, default=None, help="override keep ratio")
    ap.add_argument(
        "--mask-mode",
        choices=("informed", "random"),
        default="informed",
        help="Twist 1: Fisher-informed (default) or random iso-density mask",
    )
    ap.add_argument(
        "--random-seed",
        type=int,
        default=0,
        help="RNG seed when --mask-mode random (Twist 1)",
    )
    ap.add_argument(
        "--label",
        type=str,
        default=None,
        help="optional tag for header comment (e.g. twist1_random_s0)",
    )
    ap.add_argument("--header", type=Path, default=DEFAULT_HDR)
    ap.add_argument("--slim-header", type=Path, default=DEFAULT_SLIM)
    ap.add_argument("--bin", type=Path, default=REPO / "sw" / "emg_board_vectors.bin")
    ap.add_argument("--config", type=Path, default=DEFAULT_V2_CFG)
    ap.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="Dev cap for export-ref accuracy recompute only",
    )
    ap.add_argument(
        "--skip-accuracy",
        action="store_true",
        help="patch mask only (do not recompute export ref)",
    )
    ap.add_argument(
        "--golden-header",
        type=Path,
        default=REPO / "sw" / "golden_vectors.h",
        help="bench/ARM golden mask header",
    )
    ap.add_argument(
        "--golden-only",
        action="store_true",
        help="patch golden_vectors.h only (INA219 bench path; skip EMG headers)",
    )
    args = ap.parse_args()

    if args.keep_ratio is None:
        if not args.anchor:
            ap.error("pass --anchor A|B|C or --keep-ratio")
        keep_ratio = ANCHOR_KEEP[args.anchor]
    else:
        keep_ratio = float(args.keep_ratio)
        if not args.anchor:
            for aid, kr in ANCHOR_KEEP.items():
                if abs(kr - keep_ratio) < 1e-9:
                    args.anchor = aid
                    break
            args.anchor = args.anchor or "?"

    if not args.golden_only:
        if not args.slim_header.is_file():
            raise SystemExit(f"missing slim header {args.slim_header}")
        if not args.bin.is_file() and not args.skip_accuracy:
            raise SystemExit(f"missing {args.bin}")

    cfg_json = json.loads(args.config.read_text(encoding="utf-8"))
    item_mem_seed = int(cfg_json.get("item_mem_seed", 42))
    defs = parse_defines(args.slim_header if args.slim_header.is_file() else args.golden_header)
    cfg = HDCConfig(D=1024, seed=item_mem_seed)
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(cfg_json)
    if args.golden_only:
        subjects = cfg_json["dataset"]["subjects"]
    else:
        subjects = parse_subjects(defs, args.slim_header)

    subj_windows: List[int] = []
    protos_all = None
    if not args.golden_only and not args.skip_accuracy:
        m = re.search(
            r"emg_subj_windows\[EMG_N_SUBJECTS\] = \{([^}]+)\}",
            args.slim_header.read_text(encoding="utf-8", errors="replace"),
        )
        if not m:
            raise SystemExit("could not parse emg_subj_windows")
        subj_windows = [int(x.strip()) for x in m.group(1).split(",")]
        header_for_protos = args.header if args.header.is_file() else args.slim_header
        protos_all = load_protos_from_header(header_for_protos, cfg, len(subjects))

    mask = build_mask(
        subjects,
        cfg,
        seed,
        train_frac,
        keep_ratio,
        args.mask_mode,
        args.random_seed,
        split_kw,
    )
    emg_mask_block = fmt_mask64("emg_mask64", mask, cfg)
    golden_mask_block = fmt_mask64("golden_mask64", mask, cfg).replace(
        "EMG_WORDS64", "GOLDEN_WORDS64"
    )

    acc_x1000 = defs.get("EMG_EXPORT_REF_ACCURACY_X1000", 0)
    acc = acc_x1000 / 100000.0
    if not args.golden_only and not args.skip_accuracy and protos_all is not None:
        n = defs["EMG_BOARD_WINDOWS"]
        print(f"Recomputing export ref accuracy over {n} windows ...")
        l0, l1, l2, labels = load_levels_labels_bin(args.bin, n)
        acc = recompute_accuracy_with_mask(
            cfg, protos_all, subj_windows, l0, l1, l2, labels, mask, args.max_windows
        )
        acc_x1000 = int(round(acc * 100000))
        print(f"Export ref accuracy: {acc * 100:.2f}% (x1000={acc_x1000})")

    if args.golden_header.is_file():
        text = args.golden_header.read_text(encoding="utf-8")
        text = replace_golden_mask_block(text, golden_mask_block)
        args.golden_header.write_text(text, encoding="utf-8")
        print(f"Patched {args.golden_header}")

    if not args.golden_only:
        for path in (args.slim_header, args.header if args.header.is_file() else None):
            if path is None or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            text = replace_mask_block(text, emg_mask_block)
            if not args.skip_accuracy:
                text = update_ref_accuracy(text, acc_x1000)
                text = update_comment_accuracy(text, acc * 100)
            text = patch_header_comment(text, str(args.anchor), keep_ratio, args.label)
            path.write_text(text, encoding="utf-8")
            print(f"Patched {path}")

    print(
        f"Done anchor={args.anchor} keep={keep_ratio} mode={args.mask_mode} "
        f"mask_density={mask.mean():.4f} export_ref={acc * 100:.2f}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
