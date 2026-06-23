#!/usr/bin/env python3
"""Regenerate EMG per-subject prototypes and patch board vector headers.

The original export used bundle_majority (6-bit saturating counters) for class
prototype training. With ~20k+ windows per class the counters saturate and
prototypes collapse to all-zero, making export ref accuracy a label-skew artifact.

This script retrains prototypes with unlimited majority bundling (same threshold
rule, no saturation), patches emg_proto64 in the headers, and optionally
recomputes export ref accuracy from existing packed levels (no 4 h re-export).

Usage:
  python3 scripts/regenerate_emg_protos.py
  python3 scripts/regenerate_emg_protos.py --recompute-accuracy
  python3 scripts/regenerate_emg_protos.py --header sw/emg_board_vectors.h.full
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
    bits_to_hex_lines,
    bundle_majority_unlimited,
)
from scripts.export_emg_board_vectors import (  # noqa: E402
    DEFAULT_CONFIG,
    DATASET,
    N_CLASS,
    fmt_u64_array,
    split_train_test,
    train_prototypes_hdc_ref,
    quantize_envelope,
)

DEFAULT_HDR = REPO / "sw" / "emg_board_vectors.h.full"
DEFAULT_SLIM = REPO / "sw" / "emg_board_vectors.h"
DEFINE_RE = re.compile(r"#define\s+(\w+)\s+(\d+)U")


def parse_defines(path: Path) -> dict[str, int]:
    defs: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:80]:
        m = DEFINE_RE.search(line)
        if m:
            defs[m.group(1)] = int(m.group(2))
    return defs


def parse_subjects(defs: dict[str, int], header: Path) -> List[int]:
    text = header.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"subjects=\[([^\]]+)\]", text)
    if m:
        return [int(x.strip()) for x in m.group(1).split(",")]
    return list(range(1, int(defs.get("EMG_N_SUBJECTS", 5)) + 1))


def train_subject_protos(
    subject: int,
    cfg: HDCConfig,
    seed: int,
    train_frac: float,
) -> np.ndarray:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)
    train_q, train_labels, _, _ = split_train_test(q_all, labels, train_frac, seed)

    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    protos = train_prototypes_hdc_ref(engine, mem, cfg, train_q, train_labels)
    protos8 = np.zeros((8, cfg.D), dtype=np.uint8)
    protos8[:N_CLASS] = protos
    sums = [int(protos8[k].sum()) for k in range(N_CLASS)]
    print(f"  subject {subject}: train={train_q.shape[0]} proto bit-sums={sums}")
    return protos8


def replace_proto_block(text: str, proto_block: str) -> str:
    pat = r"static const u64 emg_proto64\[.*?\] = \{.*?\};"
    if not re.search(pat, text, flags=re.S):
        raise ValueError("emg_proto64 block not found")
    return re.sub(pat, proto_block, text, count=1, flags=re.S)


def update_ref_accuracy(text: str, acc_x1000: int) -> str:
    return re.sub(
        r"#define EMG_EXPORT_REF_ACCURACY_X1000\s+\d+U",
        f"#define EMG_EXPORT_REF_ACCURACY_X1000   {acc_x1000}U",
        text,
        count=1,
    )


def update_comment_accuracy(text: str, acc_pct: float) -> str:
    return re.sub(
        r"export_ref_accuracy=[0-9.]+%",
        f"export_ref_accuracy={acc_pct:.2f}%",
        text,
        count=1,
    )


def unpack_levels_u32(l0: int, l1: int, l2: int, cfg: HDCConfig) -> np.ndarray:
    level_w = max(1, int(math.ceil(math.log2(cfg.n_levels))))
    packed = int(l0) | (int(l1) << 32) | (int(l2) << 64)
    grid = np.zeros((cfg.n_channels, cfg.n_features), dtype=np.int32)
    for c in range(cfg.n_channels):
        for f in range(cfg.n_features):
            p = c * cfg.n_features + f
            grid[c, f] = (packed >> (level_w * p)) & ((1 << level_w) - 1)
    return grid


def load_levels_labels_bin(
    bin_path: Path, n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with bin_path.open("rb") as f:
        l0 = np.frombuffer(f.read(n * 4), dtype="<u4")
        l1 = np.frombuffer(f.read(n * 4), dtype="<u4")
        l2 = np.frombuffer(f.read(n * 4), dtype="<u4")
        labels = np.frombuffer(f.read(n), dtype=np.uint8)
    return l0, l1, l2, labels


def recompute_accuracy(
    cfg: HDCConfig,
    protos_all: np.ndarray,
    subj_windows: Sequence[int],
    l0: np.ndarray,
    l1: np.ndarray,
    l2: np.ndarray,
    labels: np.ndarray,
) -> float:
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    mask = np.ones(cfg.D, dtype=np.uint8)

    offset = 0
    total_correct = 0
    total_valid = 0
    t0 = time.time()

    for subj_idx, subj_n in enumerate(subj_windows):
        protos = protos_all[subj_idx, :N_CLASS]
        subj_correct = 0
        for i in range(subj_n):
            gi = offset + i
            if gi > 0 and gi % 50000 == 0:
                elapsed = time.time() - t0
                print(f"    accuracy pass: {gi}/{len(labels)} ({elapsed:.0f}s)", flush=True)
            grid = unpack_levels_u32(int(l0[gi]), int(l1[gi]), int(l2[gi]), cfg)
            query = engine.encode_emg_window(grid, mem)
            res = engine.classify(query, protos, mask=mask)
            gt = int(labels[gi]) - 1
            if 0 <= gt < N_CLASS:
                total_valid += 1
                if int(res.class_id) == gt:
                    subj_correct += 1
                    total_correct += 1
        print(f"    subject {subj_idx + 1}: {subj_correct}/{subj_n} correct")
        offset += subj_n

    return (total_correct / total_valid) if total_valid else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--header", type=Path, default=DEFAULT_HDR)
    ap.add_argument("--slim-header", type=Path, default=DEFAULT_SLIM)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--recompute-accuracy", action="store_true")
    ap.add_argument(
        "--skip-train",
        action="store_true",
        help="reuse emg_proto64 already present in --header (with --recompute-accuracy)",
    )
    ap.add_argument("--bin", type=Path, default=REPO / "sw" / "emg_board_vectors.bin")
    args = ap.parse_args()

    if not args.header.is_file():
        raise SystemExit(f"missing {args.header}")
    if not DATASET.is_file():
        raise SystemExit(f"missing dataset {DATASET}")

    cfg_json = json.loads(args.config.read_text(encoding="utf-8"))
    defs = parse_defines(args.header)
    cfg = HDCConfig(
        D=int(cfg_json.get("D", 1024)),
        seed=int(defs.get("EMG_ITEM_MEM_SEED", 42)),
    )
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    subjects = parse_subjects(defs, args.header)
    subj_windows = None
    m = re.search(
        r"emg_subj_windows\[EMG_N_SUBJECTS\] = \{([^}]+)\}",
        args.header.read_text(encoding="utf-8", errors="replace"),
    )
    if m:
        subj_windows = [int(x.strip()) for x in m.group(1).split(",")]

    print(f"Training prototypes for subjects {subjects} ...")
    if args.skip_train:
        text = args.header.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"emg_proto64\[.*?\] = \{(.*?)\};", text, flags=re.S)
        if not m:
            raise SystemExit("emg_proto64 block not found for --skip-train")
        hex_vals = re.findall(r"0x([0-9a-fA-F]+)ULL", m.group(1))
        n_subjects = len(subjects)
        want = n_subjects * 8 * cfg.words
        if len(hex_vals) != want:
            raise SystemExit(f"expected {want} proto u64 words, got {len(hex_vals)}")
        flat = np.array([int(v, 16) for v in hex_vals], dtype=np.uint64)
        protos_all = np.zeros((n_subjects, 8, cfg.D), dtype=np.uint8)
        for s in range(n_subjects):
            for k in range(8):
                words = flat[(s * 8 + k) * cfg.words : (s * 8 + k + 1) * cfg.words]
                protos_all[s, k] = bits_from_u64_words(words, cfg.D)
        print(f"Loaded protos from {args.header} (nonzero bits={int(np.count_nonzero(protos_all))})")
    else:
        protos_stack = []
        for subject in subjects:
            protos_stack.append(train_subject_protos(subject, cfg, seed, train_frac))
        protos_all = np.stack(protos_stack, axis=0)

        nz = int(np.count_nonzero(protos_all))
        print(f"Protos stacked shape {protos_all.shape}, nonzero bits={nz}")
        if nz == 0:
            raise SystemExit("prototype regeneration produced all-zero protos")

        proto_block = fmt_u64_array("emg_proto64", protos_all, cfg)

        for path in (args.header, args.slim_header):
            if not path.is_file():
                print(f"Skipping missing {path}")
                continue
            text = path.read_text(encoding="utf-8")
            text = replace_proto_block(text, proto_block)
            path.write_text(text, encoding="utf-8")
            print(f"Patched protos in {path}")

    if args.recompute_accuracy:
        if not args.bin.is_file():
            raise SystemExit(f"missing {args.bin} for accuracy recompute")
        if not subj_windows:
            raise SystemExit("could not parse emg_subj_windows from header")
        n = defs["EMG_BOARD_WINDOWS"]
        print(f"Recomputing export ref accuracy over {n} windows ...")
        l0, l1, l2, labels = load_levels_labels_bin(args.bin, n)
        acc = recompute_accuracy(cfg, protos_all, subj_windows, l0, l1, l2, labels)
        acc_x1000 = int(round(acc * 100000))
        print(f"New export ref accuracy: {acc * 100:.2f}% (x1000={acc_x1000})")
        for path in (args.header, args.slim_header):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            text = update_ref_accuracy(text, acc_x1000)
            text = update_comment_accuracy(text, acc * 100)
            path.write_text(text, encoding="utf-8")
            print(f"Updated ref accuracy in {path}")
    else:
        print("Skipping accuracy recompute (pass --recompute-accuracy to update ref)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
