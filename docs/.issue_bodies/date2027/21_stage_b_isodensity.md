## Priority: P0 · Paper 2 · **Required for strong Paper 2**

Stage-B (dense-support) iso-density ablation — falsification test for “support, not score.”

## Goal

Run the same iso-density comparison as Twist 1 (informed vs random-all vs
random-support) using the **Stage-B BSC encoder** (~90% spatial mean), not the
RTL encoder. Determines whether ranking criteria separate when active support is dense.

## Requirements

- [ ] Add `python_ref/run_twist1_stage_b.py` (fork `run_twist1_sweep.py`, encode via `repro/stage_b_bsc.py`)
- [ ] Keep ratios: **0.125, 0.25, 0.5** (minimum); optional full grid
- [ ] 30 random seeds per keep at 0.125 (match existing Twist 1 protocol)
- [ ] Report: informed, random-all mean±std, random-support, gap (pp)
- [ ] Subject-level bootstrap CI + Wilcoxon (reuse `tools/subject_level_stats.py`)
- [ ] Output: `results/protocol_v2/twist1_stage_b/twist1_results.json` + README

## Done when

- [ ] JSON committed; gap and CI documented in `results/.../README.md`
- [ ] Decision recorded: criteria **tie** vs **separate** on Stage-B at keep=128
- [ ] Blocker cleared for manuscript integration (#36)

## Commands (draft)

```bash
python python_ref/run_twist1_stage_b.py --keep 0.125 --seeds 30 \
  --out results/protocol_v2/twist1_stage_b/keep_0125
```

## References

- Plan: [SPLIT_PAPER_PLAN.md §4 S1](docs/SPLIT_PAPER_PLAN.md)
- Existing RTL run: `python_ref/run_twist1_sweep.py`, `results/twist1/`

## Blocks

- #22 Stage-B ranking baselines (after keep=0.125 baseline exists)
