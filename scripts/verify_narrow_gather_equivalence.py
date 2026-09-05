#!/usr/bin/env python3
"""Prove the baked-permutation narrow datapath is bit-exact to masked full-width classify.

H1 / issue #28, Option E. Instead of gating a 1024-bit datapath, hardwire the K
Fisher-selected bit positions into the AM operand routing so the AM is physically
K bits wide:

    narrow_query[i]    = query[SEL[i]]
    narrow_proto[k][i] = proto[k][SEL[i]]          # applied offline by software
    dist[k]            = popcount(narrow_query ^ narrow_proto[k])

That is identical to `popcount((query ^ proto[k]) & mask)` because popcount is
invariant to relabeling of bit positions. So the narrow datapath inherits the
free-choice Fisher accuracy exactly — no accuracy gate to clear.

`SEL` is a synthesis-time constant, so the gather is pure wiring (no muxes, 0 LUT),
unlike the runtime-configurable gather rejected in #28.

This script checks the identity numerically on real cohort data, per-window and on
pooled accuracy, and is the reference for the #30 co-sim golden model.

Usage:
  python3 scripts/verify_narrow_gather_equivalence.py
  python3 scripts/verify_narrow_gather_equivalence.py --keep 0.125 0.25 --max-windows 20000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "python_ref"))

from hdc_ref import mask_from_scores, per_bit_fisher_scores  # noqa: E402

BITS_PER_WORD = 64
N_CLASS = 5
DEFAULT_CACHE = REPO / "results" / "protocol_v2" / "twist1_silicon" / "cohort_cache.npz"
DEFAULT_OUT = REPO / "results" / "narrow_rtl" / "narrow_gather_equivalence.json"


def masked_full_dists(query: np.ndarray, protos: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Baseline popcount_am: full-width XOR, then mask."""
    return ((query[None, :] ^ protos) & mask[None, :]).sum(axis=1)


def narrow_dists(query_n: np.ndarray, protos_n: np.ndarray) -> np.ndarray:
    """Option E: pre-gathered operands, no mask, K-bit datapath."""
    return (query_n[None, :] ^ protos_n).sum(axis=1)


def argmin_first(d: np.ndarray) -> int:
    """NumPy argmin semantics: first index wins on a tie (matches the RTL)."""
    return int(np.argmin(d))


def main() -> int:
    ap = argparse.ArgumentParser(description="Narrow gather equivalence (issue #28, Option E)")
    ap.add_argument("--keep", type=float, nargs="+", default=[0.125, 0.25, 0.5])
    ap.add_argument("--cohort-cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--max-windows", type=int, default=20_000)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.cohort_cache.is_file():
        raise SystemExit(f"missing {args.cohort_cache}")

    data = np.load(args.cohort_cache, allow_pickle=True)
    all_hvs = [np.asarray(h) for h in data["test_hvs"]]
    all_labels = [np.asarray(l) for l in data["test_labels"]]
    all_protos = [np.asarray(p) for p in data["protos"]]
    D = all_hvs[0].shape[1]

    flat = np.concatenate([h for h in all_hvs if len(h)], axis=0)
    flat_lab = np.concatenate([l for l in all_labels if len(l)], axis=0)
    scores = per_bit_fisher_scores(flat, flat_lab.astype(np.int32))

    rows: List[Dict[str, object]] = []
    all_ok = True

    for keep in args.keep:
        mask = mask_from_scores(scores, keep, informed=True).astype(np.uint8)
        sel = np.flatnonzero(mask)            # SEL[] — synthesis-time constant
        k_bits = int(sel.size)
        words = int(np.ceil(k_bits / BITS_PER_WORD))

        dist_mismatch = 0
        pred_mismatch = 0
        checked = 0
        correct_full = 0
        correct_narrow = 0
        valid = 0
        remaining = args.max_windows

        for hvs, labels, protos in zip(all_hvs, all_labels, all_protos):
            n = hvs.shape[0]
            if remaining is not None:
                n = min(n, remaining)
                if n <= 0:
                    break
            protos_n = protos[:, sel]
            for i in range(n):
                d_full = masked_full_dists(hvs[i], protos, mask)
                d_narrow = narrow_dists(hvs[i][sel], protos_n)
                checked += 1
                if not np.array_equal(d_full, d_narrow):
                    dist_mismatch += 1
                p_full = argmin_first(d_full)
                p_narrow = argmin_first(d_narrow)
                if p_full != p_narrow:
                    pred_mismatch += 1
                gt = int(labels[i]) - 1
                if 0 <= gt < N_CLASS:
                    valid += 1
                    correct_full += p_full == gt
                    correct_narrow += p_narrow == gt
            if remaining is not None:
                remaining -= n

        ok = dist_mismatch == 0 and pred_mismatch == 0
        all_ok &= ok
        acc_full = 100 * correct_full / valid if valid else 0.0
        acc_narrow = 100 * correct_narrow / valid if valid else 0.0
        rows.append(
            {
                "keep_ratio": keep,
                "k_bits": k_bits,
                "am_words": words,
                "windows_checked": checked,
                "distance_vector_mismatches": dist_mismatch,
                "prediction_mismatches": pred_mismatch,
                "accuracy_masked_full_pct": round(acc_full, 4),
                "accuracy_narrow_gather_pct": round(acc_narrow, 4),
                "bit_exact": ok,
            }
        )
        print(
            f"keep={keep}: K={k_bits} bits ({words} words)  "
            f"dist mismatches={dist_mismatch}  pred mismatches={pred_mismatch}  "
            f"acc full={acc_full:.4f}%  narrow={acc_narrow:.4f}%  "
            f"{'BIT-EXACT' if ok else 'MISMATCH'}",
            flush=True,
        )

    report = {
        "issue": 28,
        "option": "E — baked bit-permutation + narrow AM",
        "claim": "popcount is invariant to bit relabeling, so a hardwired gather of the "
                 "Fisher-selected positions is bit-exact to masked full-width classify",
        "D": D,
        "bits_per_word": BITS_PER_WORD,
        "all_bit_exact": bool(all_ok),
        "keep_grid": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\n{'ALL BIT-EXACT' if all_ok else 'FAILURES PRESENT'} -> {args.out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
