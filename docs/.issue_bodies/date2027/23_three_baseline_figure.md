## Priority: P1 · Paper 2 · Clarity / strong figure

Hero figure: informed vs random-all vs random-support at fixed keep.

## Goal

Single panel (or small multiples) showing the **three iso-density baselines** at
keep=0.125 for RTL encoder (and optionally Stage-B side-by-side after #21).

## Requirements

- [ ] Extend `python_ref/plot_results.py` — three bars + error bars on random-all
- [ ] Values from `twist1` / `protocol_v2` JSON (72.65 / 65.75±3.20 / 71.45)
- [ ] Paper-mode PDF: `results/figures/twist1_three_baselines_keep0125.pdf`
- [ ] Copy to `Research-paper/figures/` when integrating (#36)

## Done when

- [ ] Figure committed; caption draft in issue comment
- [ ] Replaces or supplements `twist1_informed_vs_random_keep0125.pdf`

## Blocked by

- None for RTL (data exists); Stage-B panel blocked on #21
