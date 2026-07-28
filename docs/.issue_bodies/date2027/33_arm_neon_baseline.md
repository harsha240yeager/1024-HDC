## Priority: P2 · Paper 1 · Optional

ARM HDC baseline with **NEON** popcount / vectorized XOR.

## Goal

Close “unfair software baseline” criticism; narrow reported PL speedup if ARM gets faster.

## Requirements

- [ ] Extend `sw/libhdc_arm_ref` or new variant with NEON intrinsics
- [ ] Same windows/protocol as `run_arm_hdc_baseline.py`
- [ ] Compare latency vs current `-O2` baseline (818 µs/w)
- [ ] Output: `results/baselines/arm_hdc_neon_results.json`

## Done when

- [ ] ≥10% ARM speedup vs existing baseline **or** document marginal gain in paper

## Gate

Optional — do after P0/P1 track unless reviewer rehearsal flags ARM fairness.
