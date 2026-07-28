## Priority: P0 · Paper 2 · **Required for strong Paper 2**

Six ranking criteria on Stage-B encoder at fixed keep — do they still tie?

## Goal

Repeat `run_ranking_baselines.py` logic with **Stage-B encoding** at keep=0.125.
If Fisher, variance, MI, etc. **diverge** in predictions, Paper 2 novelty rises;
if they still tie, report as “universal under dense support.”

## Requirements

- [ ] Extend `run_twist1_stage_b.py` or add `run_ranking_baselines_stage_b.py`
- [ ] Same six criteria as Paper (Fisher, variance/MI tie, class-mean, prototype disagreement, entropy)
- [ ] Jaccard overlap vs Fisher mask; per-window prediction agreement
- [ ] Output: `results/protocol_v2/twist1_stage_b/ranking_baselines_results.json`

## Done when

- [ ] Table: criterion × spatial mean accuracy (expect tie or documented separation)
- [ ] Jaccard range reported
- [ ] One-paragraph “dense support” conclusion ready for Sec. V-D extension

## Blocked by

- #21 Stage-B iso-density (encoder path must exist)

## References

- `python_ref/run_ranking_baselines.py`
- `results/protocol_v2/ranking_baselines/`
