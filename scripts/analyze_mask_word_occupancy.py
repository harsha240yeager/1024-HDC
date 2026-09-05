#!/usr/bin/env python3
"""Word-level mask occupancy analysis for the H1 narrow/gated datapath (issue #28).

`popcount_am` walks WORDS=16 64-bit words per prototype regardless of the mask.
A word-skipping optimisation only pays off if whole 64-bit words are dead
(mask==0). This script measures how kept bits distribute across words for:

  * value-table active support (structural ceiling, item mem seed 42)
  * random iso-density masks (Twist 1 silicon path, seeds 0..N)
  * Fisher-ranked masks, when a cached cohort is available

Output feeds docs/H1_narrow_datapath_design.md.

Usage:
  python3 scripts/analyze_mask_word_occupancy.py
  python3 scripts/analyze_mask_word_occupancy.py --keep 0.125 0.25 0.5
  python3 scripts/analyze_mask_word_occupancy.py --cohort-cache results/protocol_v2/twist1_silicon/cohort_cache.npz
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "python_ref"))

from hdc_ref import HDCConfig, ItemMemory, mask_from_scores  # noqa: E402

BITS_PER_WORD = 64
DEFAULT_OUT = REPO / "results" / "narrow_rtl" / "mask_word_occupancy.json"


def word_stats(mask: np.ndarray, bits_per_word: int = BITS_PER_WORD) -> Dict[str, float]:
    """Per-word live-bit statistics for one mask."""
    n_words = mask.shape[0] // bits_per_word
    per_word = mask.reshape(n_words, bits_per_word).sum(axis=1)
    dead = int((per_word == 0).sum())
    return {
        "n_keep": int(mask.sum()),
        "n_words": n_words,
        "dead_words": dead,
        "live_words": n_words - dead,
        "min_live_bits": int(per_word.min()),
        "max_live_bits": int(per_word.max()),
        "mean_live_bits": round(float(per_word.mean()), 2),
        "word_skip_saving_pct": round(100.0 * dead / n_words, 2),
        "per_word_live": per_word.astype(int).tolist(),
    }


def active_support_mask(cfg: HDCConfig) -> np.ndarray:
    """Positions that can ever change under any input (value item memory)."""
    mem = ItemMemory(cfg)
    value = np.asarray(mem.value)
    varying = (value != value[0]).any(axis=0)
    return varying.astype(np.uint8)


def fisher_scores_from_cache(cache_path: Path, cfg: HDCConfig) -> np.ndarray | None:
    """Per-bit class-separability scores from a cached cohort (design proxy only)."""
    if not cache_path.is_file():
        return None
    data = np.load(cache_path, allow_pickle=True)
    hvs = np.concatenate([np.asarray(h) for h in data["test_hvs"] if len(h)], axis=0)
    labels = np.concatenate([np.asarray(l) for l in data["test_labels"] if len(l)], axis=0)
    from hdc_ref import per_bit_fisher_scores

    return per_bit_fisher_scores(hvs, labels.astype(np.int32))


def main() -> int:
    ap = argparse.ArgumentParser(description="H1 mask word-occupancy analysis")
    ap.add_argument("--keep", type=float, nargs="+", default=[0.125, 0.25, 0.5])
    ap.add_argument("--random-seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--item-mem-seed", type=int, default=42)
    ap.add_argument("--D", type=int, default=1024)
    ap.add_argument(
        "--cohort-cache",
        type=Path,
        default=REPO / "results" / "protocol_v2" / "twist1_silicon" / "cohort_cache.npz",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    cfg = HDCConfig(D=args.D, seed=args.item_mem_seed)
    report: Dict[str, object] = {
        "issue": 28,
        "D": args.D,
        "bits_per_word": BITS_PER_WORD,
        "item_mem_seed": args.item_mem_seed,
    }

    support = active_support_mask(cfg)
    report["active_support"] = word_stats(support)
    print(
        f"Active support (value table, seed {args.item_mem_seed}): "
        f"{int(support.sum())}/{args.D} bits, "
        f"{report['active_support']['dead_words']} dead words"
    )

    keep_rows: List[Dict[str, object]] = []
    for keep in args.keep:
        random_stats = []
        for seed in args.random_seeds:
            mask = mask_from_scores(
                np.zeros(args.D),
                keep,
                rng=np.random.default_rng(seed),
                informed=False,
            ).astype(np.uint8)
            st = word_stats(mask)
            st.pop("per_word_live")
            st["seed"] = seed
            random_stats.append(st)

        dead_counts = [s["dead_words"] for s in random_stats]
        row: Dict[str, object] = {
            "keep_ratio": keep,
            "n_keep": random_stats[0]["n_keep"],
            "random": {
                "seeds": random_stats,
                "mean_dead_words": round(float(np.mean(dead_counts)), 2),
                "max_dead_words": int(max(dead_counts)),
                "mean_live_bits_per_word": random_stats[0]["mean_live_bits"],
            },
        }
        print(
            f"keep={keep}: random masks -> mean dead words "
            f"{row['random']['mean_dead_words']}/16 "
            f"(max {row['random']['max_dead_words']}), "
            f"{random_stats[0]['mean_live_bits']} live bits/word"
        )
        keep_rows.append(row)

    scores = fisher_scores_from_cache(args.cohort_cache, cfg)
    if scores is not None:
        print(f"Fisher-ranked masks from {args.cohort_cache.name}")
        for row in keep_rows:
            mask = mask_from_scores(scores, row["keep_ratio"], informed=True).astype(np.uint8)
            st = word_stats(mask)
            row["fisher"] = st
            print(
                f"keep={row['keep_ratio']}: fisher -> {st['dead_words']}/16 dead words, "
                f"live bits/word min {st['min_live_bits']} max {st['max_live_bits']}"
            )
    else:
        print(f"No cohort cache at {args.cohort_cache} — skipping Fisher rows")

    report["keep_grid"] = keep_rows
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
