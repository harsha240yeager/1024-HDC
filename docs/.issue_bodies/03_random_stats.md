## Priority: P1 (blocked by #1)

Expand random-mask evaluation and add subject-level statistics.

## Requirements

- Python: **20–30** random masks per keep ratio
- FPGA: **≥5** random masks (mask reprogram only, no resynth)
- Stats: paired subject-level mean/median/std, **95% CI (bootstrap over subjects)**, p-value
- **Do not** treat window count as i.i.d. samples

## Result table

| Keep bits | Fisher mean | Random mean | Gap | 95% CI | p-value |

## Scripts

- Extend `run_twist1_sweep.py`, `run_twist1_board.sh`
- Add `python_ref/tools/subject_level_stats.py`

Plan: [Phase 3](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-3--expand-random-mask-baseline--statistics)
