# Subject-level statistics (Twist 1 iso-density)

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
