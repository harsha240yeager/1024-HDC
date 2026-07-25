# Subject-level statistics (Twist 1 iso-density)

Source: `results/protocol_v2/twist1_keep0125_30seed/twist1_results.json`
Generated: 2026-07-25T07:55:21Z
Protocol: **HDC-2** · keep=0.125 (128 bits) · 30 random seeds

**Unit of analysis: subject (n=5)** — not windows.

## Paired gap (informed − random), percentage points

| Statistic | Value |
|-----------|-------|
| Mean gap | **+6.90 pp** |
| Median gap | +6.54 pp |
| Std (sample) | 3.80 pp |
| Min / max | +1.79 / +11.32 pp |
| Bootstrap 95% CI (mean) | [+4.04, +9.76] pp |
| CI excludes 0? | yes |
| Target (≥ 5 pp) met by mean? | yes |

## Hypothesis tests (paired over subjects)

- Subjects with positive gap: **5/5**
- Wilcoxon signed-rank (two-sided): p = 0.0625
- Wilcoxon signed-rank (one-sided, greater): p = 0.03125
- Paired t-test (one-sided, greater): p = 0.007654

With n=5, the exact two-sided Wilcoxon floor when all gaps are positive is 1/16 = 0.0625; one-sided floor is 1/32 = 0.03125. Report the CI and the 5/5 positive-gap count alongside p-values.

## Per-subject gaps

| Subject | Informed | Random mean | Gap (pp) |
|---------|----------|-------------|----------|
| S1 | 76.90% | 70.36% | +6.54 |
| S2 | 70.03% | 58.71% | +11.32 |
| S3 | 80.98% | 71.17% | +9.81 |
| S4 | 63.05% | 61.26% | +1.79 |
| S5 | 72.28% | 67.23% | +5.05 |
