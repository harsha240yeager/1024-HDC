## Priority: P2 · Paper 1

Pareto figure + script: keep ratio vs LUT / µJ / µs (baseline vs narrow RTL).

## Goal

Publication-ready figure for Paper 1 / combined DATE Discussion.

## Requirements

- [ ] Add `scripts/compare_narrow_vs_baseline_lut.sh` — parse Vivado util reports
- [ ] Extend `python_ref/plot_results.py` or new `plot_narrow_pareto.py`
- [ ] Output: `results/figures/narrow_vs_baseline_pareto.pdf`
- [ ] Caption draft: heterogeneity vs baseline null (fixed-width) RTL

## Done when

- [ ] Figure in `Research-paper/figures/` via integration #36
- [ ] Numbers traceable in committed CSV

## Blocked by

- #31 board + util data
