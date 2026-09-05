# Narrow / gated datapath (H1) — design evidence

Design-stage measurements backing [#28](https://github.com/harsha240yeager/1024-HDC/issues/28).
Full argument and micro-architecture spec: `docs/H1_narrow_datapath_design.md`.

Implementation, synthesis, and board numbers land under #29/#31 and will be added here.

## Files

| File | Produced by | What it answers |
|---|---|---|
| `mask_word_occupancy.json` | `scripts/analyze_mask_word_occupancy.py` | Do whole 64-bit words go dead under pruning? |
| `word_blocked_mask_eval.json` | `scripts/eval_word_blocked_mask.py` | What does word-granular mask selection cost in accuracy? |

## Regenerate

```bash
python3 scripts/analyze_mask_word_occupancy.py
python3 scripts/eval_word_blocked_mask.py --max-windows 40000
```

`eval_word_blocked_mask.py` needs the cached cohort at
`results/protocol_v2/twist1_silicon/cohort_cache.npz`; build it with
`python3 python_ref/predict_twist1_silicon_seeds.py --from-dataset`.

## Headline findings

**1. Scattered masks never free a word.** Zero dead 64-bit words at every keep ratio, for the value-table
active support, random iso-density masks (seeds 0–9), and Fisher-ranked masks. Kept bits are uniformly
scattered because the item memory is random, so any skip-the-dead-word optimisation saves exactly 0%.
This is the measured refutation of the obvious approach and the reason the mask must be made
*structurally* sparse.

**2. Word-blocked selection is free at keep=0.25.** Restricting selection to whole words (which makes
skipping work by construction) costs 0.00 pp vs free-choice at keep=0.25 while removing 75% of AM
cycles — 264 → 72 cycles, i.e. core latency 2.87 µs → 0.95 µs @ 100 MHz.

| keep | Words | Cycle reduction | Free-choice | Word-blocked | Δ | Random |
|---|---|---|---|---|---|---|
| 0.125 | 2/16 | −88% | 77.68% | 73.16% | −4.53 pp | 66.61% |
| 0.25 | 4/16 | −75% | 74.28% | **74.28%** | **0.00 pp** | 68.62% |
| 0.5 | 8/16 | −50% | 74.28% | 72.32% | −1.96 pp | 70.58% |

## Scope limits

Accuracy figures here are a **design-time relative comparison**, not paper numbers. Scores are derived
from the cached cohort, so every arm is optimistic — that is why free-choice at keep=0.125 (77.68%)
exceeds the 74.28% unpruned reference. The bias is shared across arms, so the blocked-vs-free delta is
the usable signal, and it is conservative: free-choice can exploit per-bit leakage that word-granular
selection cannot. Reportable numbers come from the TRAIN-Fisher path under #29/#31.
