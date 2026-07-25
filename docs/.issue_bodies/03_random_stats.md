## Priority: P1

Expand random-mask evaluation and add subject-level statistics.

## Requirements

- [x] Python: **20–30** random masks per keep ratio (`twist1_keep0125_30seed/`, 30 seeds)
- [ ] FPGA: **≥5** random masks (seed 0 done; seeds 1–9 deferred — JTAG)
- [x] Stats: paired subject-level mean/median/std, **95% CI (bootstrap over subjects)**, p-value
- [x] **Do not** treat window count as i.i.d. samples

## Result (Python, keep=128, HDC-2 S1–S5)

| Keep | Fisher | Random | Gap | 95% CI (subjects) | Wilcoxon (1-sided) |
|------|--------|--------|-----|-------------------|--------------------|
| 128 | 72.65% | 65.75% | +6.90 pp | [+4.04, +9.76] | p=0.03125 (5/5 +) |

Tool: `python_ref/tools/subject_level_stats.py`

Plan: [Phase 3](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-3--expand-random-mask-baseline--statistics)
