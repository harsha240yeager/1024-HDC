# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)

**Issue:** [#26](https://github.com/harsha240yeager/1024-HDC/issues/26) (closed)  
**Windows:** 493,512 (HDC-2 pooled cohort)  
**Informed (anchor C):** 72.84% board  
**Automation:** `scripts/run_one_silicon_seed_board.sh`, `scripts/run_silicon_seeds_board_stepwise.sh`, `scripts/merge_measured_silicon_seeds.py`

## Measured cohort (seeds 0–9, board)

| Stat | Value |
|------|-------|
| Mean random board acc | **65.40%** |
| Mean gap vs informed | **+7.45 ± 2.59 pp** |
| Range (gap) | +3.61 … +11.29 pp |

| Seed | Board % | Gap (pp) | Artifact |
|------|---------|----------|----------|
| 0 | 62.51 | +10.33 | `random_seed_0/board_emg_replay.txt` |
| 1 | 64.58 | +8.26 | `random_seed_1/` |
| 2 | 67.63 | +5.21 | `random_seed_2/` |
| 3 | 62.77 | +10.07 | `random_seed_3/` |
| 4 | 66.00 | +6.84 | `random_seed_4/` |
| 5 | 61.55 | +11.29 | `random_seed_5/` |
| 6 | 64.62 | +8.22 | `random_seed_6/` |
| 7 | 67.56 | +5.28 | `random_seed_7/` |
| 8 | 69.23 | +3.61 | `random_seed_8/` |
| 9 | 67.48 | +5.36 | `random_seed_9/` |

Summary: `seed_summary.json` · campaign log: `board_stepwise.log`

## Re-run one seed

```bash
unset HDC_NARROW HDC_VIVADO_ROOT
bash scripts/run_one_silicon_seed_board.sh 7
python3 scripts/merge_measured_silicon_seeds.py
```
