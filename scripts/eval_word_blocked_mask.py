#!/usr/bin/env python3
"""Word-blocked vs free-choice mask accuracy — H1 design feasibility (issue #28).

`popcount_am` iterates whole 64-bit words. Word-level skipping only helps if the
mask is *block structured* (whole words kept or dropped). This script measures
what that structural constraint costs in accuracy at matched density.

Arms at equal kept-bit count:
  free     — top-K bits anywhere (current design)
  blocked  — top-(K/64) whole words by summed score (word-skippable)
  random   — iso-density scattered reference

**Scope:** design-time *relative* comparison. Scores are derived from the cached
cohort, so absolute values are optimistic for every arm equally; the free-vs-
blocked delta is the decision input. Paper numbers come from the TRAIN-Fisher
path in #29/#31.

Usage:
  python3 scripts/eval_word_blocked_mask.py
  python3 scripts/eval_word_blocked_mask.py --keep 0.125 0.25 --max-windows 50000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "python_ref"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    mask_from_scores,
    per_bit_fisher_scores,
)

BITS_PER_WORD = 64
N_CLASS = 5
DEFAULT_CACHE = REPO / "results" / "protocol_v2" / "twist1_silicon" / "cohort_cache.npz"
DEFAULT_OUT = REPO / "results" / "narrow_rtl" / "word_blocked_mask_eval.json"


def blocked_mask_from_scores(scores: np.ndarray, keep_ratio: float) -> np.ndarray:
    """Keep whole 64-bit words with the highest summed score."""
    D = scores.shape[0]
    n_words = D // BITS_PER_WORD
    n_keep_words = max(1, int(round(n_words * keep_ratio)))
    word_scores = scores.reshape(n_words, BITS_PER_WORD).sum(axis=1)
    top = np.argsort(-word_scores)[:n_keep_words]
    mask = np.zeros(D, dtype=np.uint8)
    for w in top:
        mask[w * BITS_PER_WORD : (w + 1) * BITS_PER_WORD] = 1
    return mask


def accuracy(
    engine: HDCEngine,
    all_hvs: List[np.ndarray],
    all_labels: List[np.ndarray],
    all_protos: List[np.ndarray],
    mask: np.ndarray,
    max_windows: int | None,
) -> float:
    correct = 0
    valid = 0
    remaining = max_windows
    for hvs, labels, protos in zip(all_hvs, all_labels, all_protos):
        n = hvs.shape[0]
        if remaining is not None:
            n = min(n, remaining)
            if n <= 0:
                break
        for i in range(n):
            pred = engine.classify(hvs[i], protos, mask=mask).class_id
            gt = int(labels[i]) - 1
            if 0 <= gt < N_CLASS:
                valid += 1
                if int(pred) == gt:
                    correct += 1
        if remaining is not None:
            remaining -= n
    return (correct / valid) if valid else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Word-blocked mask feasibility (issue #28)")
    ap.add_argument("--keep", type=float, nargs="+", default=[0.125, 0.25, 0.5])
    ap.add_argument("--cohort-cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--max-windows", type=int, default=50_000)
    ap.add_argument("--random-seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.cohort_cache.is_file():
        raise SystemExit(
            f"missing {args.cohort_cache}\n"
            "  build it: python3 python_ref/predict_twist1_silicon_seeds.py --from-dataset"
        )

    print(f"Loading cohort cache {args.cohort_cache.name} ...", flush=True)
    data = np.load(args.cohort_cache, allow_pickle=True)
    all_hvs = [np.asarray(h) for h in data["test_hvs"]]
    all_labels = [np.asarray(l) for l in data["test_labels"]]
    all_protos = [np.asarray(p) for p in data["protos"]]

    D = all_hvs[0].shape[1]
    cfg = HDCConfig(D=D)
    engine = HDCEngine(cfg)

    flat_hvs = np.concatenate([h for h in all_hvs if len(h)], axis=0)
    flat_labels = np.concatenate([l for l in all_labels if len(l)], axis=0)
    scores = per_bit_fisher_scores(flat_hvs, flat_labels.astype(np.int32))

    unpruned = accuracy(
        engine, all_hvs, all_labels, all_protos,
        np.ones(D, dtype=np.uint8), args.max_windows,
    )
    print(f"Unpruned reference: {unpruned * 100:.2f}%")

    rows: List[Dict[str, object]] = []
    for keep in args.keep:
        t0 = time.time()
        free = mask_from_scores(scores, keep, informed=True).astype(np.uint8)
        blocked = blocked_mask_from_scores(scores, keep)

        free_acc = accuracy(engine, all_hvs, all_labels, all_protos, free, args.max_windows)
        blocked_acc = accuracy(engine, all_hvs, all_labels, all_protos, blocked, args.max_windows)

        rand_accs = []
        for seed in args.random_seeds:
            rmask = mask_from_scores(
                scores, keep, rng=np.random.default_rng(seed), informed=False
            ).astype(np.uint8)
            rand_accs.append(
                accuracy(engine, all_hvs, all_labels, all_protos, rmask, args.max_windows)
            )

        n_words_kept = int(blocked.sum() // BITS_PER_WORD)
        row = {
            "keep_ratio": keep,
            "n_keep_free": int(free.sum()),
            "n_keep_blocked": int(blocked.sum()),
            "words_kept_blocked": n_words_kept,
            "cycle_reduction_blocked_pct": round(100.0 * (1 - n_words_kept / (D // BITS_PER_WORD)), 2),
            "free_accuracy_pct": round(free_acc * 100, 4),
            "blocked_accuracy_pct": round(blocked_acc * 100, 4),
            "random_mean_accuracy_pct": round(float(np.mean(rand_accs)) * 100, 4),
            "blocked_minus_free_pp": round((blocked_acc - free_acc) * 100, 4),
            "blocked_minus_random_pp": round((blocked_acc - float(np.mean(rand_accs))) * 100, 4),
            "elapsed_s": round(time.time() - t0, 1),
        }
        rows.append(row)
        print(
            f"keep={keep}: free={row['free_accuracy_pct']:.2f}%  "
            f"blocked={row['blocked_accuracy_pct']:.2f}%  "
            f"(delta {row['blocked_minus_free_pp']:+.2f} pp)  "
            f"random={row['random_mean_accuracy_pct']:.2f}%  "
            f"cycles -{row['cycle_reduction_blocked_pct']:.0f}%",
            flush=True,
        )

    report = {
        "issue": 28,
        "scope": "design-time relative comparison; scores from cached cohort (optimistic, equal bias across arms)",
        "D": D,
        "bits_per_word": BITS_PER_WORD,
        "n_windows_evaluated": min(int(flat_labels.shape[0]), args.max_windows or 10**9),
        "unpruned_accuracy_pct": round(unpruned * 100, 4),
        "keep_grid": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
