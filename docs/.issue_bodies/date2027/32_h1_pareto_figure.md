## Priority: P2 · Paper 1

Pareto figure + script: keep ratio vs LUT / µJ / µs (baseline vs narrow RTL).

## Goal

Publication-ready figure for Paper 1 / combined DATE Discussion.

## Requirements

- [x] `scripts/compare_narrow_vs_baseline_lut.sh` — parse Vivado util reports
- [x] `python_ref/plot_narrow_pareto.py` + `scripts/plot_issue32_pareto.sh`
- [x] Output: `results/figures/narrow_vs_baseline_pareto.pdf`
- [x] Caption draft: `narrow_vs_baseline_pareto_caption.txt`

## Done when

- [ ] Figure in `Research-paper/figures/` via integration #36
- [x] Numbers traceable in `results/figures/narrow_vs_baseline_pareto.csv`

## Blocked by

- #31 board + util data
