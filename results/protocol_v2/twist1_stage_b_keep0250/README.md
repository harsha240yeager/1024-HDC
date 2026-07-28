# Twist 1 — Stage B informed vs random @ iso-density (HDC-2)

Generated: 2026-07-28T12:24:55Z
Engine: **Stage B BSC** (4-channel spatial records, D=1024)
Protocol: **HDC-2** · keep=0.25 (256 bits)
Random seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]

## Headline (5-subject mean)

| Mask | Spatial mean accuracy |
|------|----------------------|
| Unpruned (keep=1.0) | **89.46%** |
| Fisher informed | **89.34%** |
| Random (mean ± std over seeds) | **88.32% ± 2.19 pp** |
| **Gap (informed − random)** | **+1.02 pp** |

Target ≥ 5 pp: **FAIL**

Compare hdc_ref Twist 1 @ same keep: **+6.90 pp** ([`twist1_keep0125_30seed/`](../twist1_keep0125_30seed/))

Full keep grid + decision: [`twist1_stage_b/`](../twist1_stage_b/)

## Per subject

| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |
|---------|----------|---------------|----------|----------|
| S1 | 94.39% | 93.30% | +1.09 | 94.39% |
| S2 | 88.10% | 85.18% | +2.92 | 88.10% |
| S3 | 89.35% | 89.26% | +0.09 | 89.35% |
| S4 | 88.07% | 86.77% | +1.31 | 88.07% |
| S5 | 86.78% | 87.09% | -0.32 | 87.39% |

## Subject-level statistics

Source: `results/protocol_v2/twist1_stage_b_keep0250/twist1_results.json`
Generated: 2026-07-28T12:25:05Z
Protocol: **HDC-2** · keep=0.25 (256 bits) · 30 random seeds

**Unit of analysis: subject (n=5)** — not windows.

## Paired gap (informed − random), percentage points

| Statistic | Value |
|-----------|-------|
| Mean gap | **+1.02 pp** |
| Median gap | +1.09 pp |
| Std (sample) | 1.26 pp |
| Min / max | -0.32 / +2.92 pp |
| Bootstrap 95% CI (mean) | [+0.09, +2.03] pp |
| CI excludes 0? | yes |
| Target (≥ 5 pp) met by mean? | no |

## Hypothesis tests (paired over subjects)

- Subjects with positive gap: **4/5**
- Wilcoxon signed-rank (two-sided): p = 0.1875
- Wilcoxon signed-rank (one-sided, greater): p = 0.09375
- Paired t-test (one-sided, greater): p = 0.07253

With n=5, the exact two-sided Wilcoxon floor when all gaps are positive is 1/16 = 0.0625; one-sided floor is 1/32 = 0.03125. Report the CI and the 5/5 positive-gap count alongside p-values.

## Per-subject gaps

| Subject | Informed | Random mean | Gap (pp) |
|---------|----------|-------------|----------|
| S1 | 94.39% | 93.30% | +1.09 |
| S2 | 88.10% | 85.18% | +2.92 |
| S3 | 89.35% | 89.26% | +0.09 |
| S4 | 88.07% | 86.77% | +1.31 |
| S5 | 86.78% | 87.09% | -0.32 |

## Regenerate

```bash
python3 python_ref/run_twist1_stage_b_sweep.py --quick
python3 python_ref/run_twist1_stage_b_sweep.py
```

Stage B baseline: [`stage_b_hdc2/`](../stage_b_hdc2/)
