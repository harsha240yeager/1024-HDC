# Subject-level statistics (Twist 1 iso-density)

Source: `results/protocol_v2/twist1_stage_b_keep0500/twist1_results.json`
Generated: 2026-07-28T12:32:35Z
Protocol: **HDC-2** · keep=0.5 (512 bits) · 30 random seeds

**Unit of analysis: subject (n=5)** — not windows.

## Paired gap (informed − random), percentage points

| Statistic | Value |
|-----------|-------|
| Mean gap | **+0.50 pp** |
| Median gap | +0.59 pp |
| Std (sample) | 0.56 pp |
| Min / max | -0.16 / +1.05 pp |
| Bootstrap 95% CI (mean) | [+0.05, +0.94] pp |
| CI excludes 0? | yes |
| Target (≥ 5 pp) met by mean? | no |

## Hypothesis tests (paired over subjects)

- Subjects with positive gap: **3/5**
- Wilcoxon signed-rank (two-sided): p = 0.3125
- Wilcoxon signed-rank (one-sided, greater): p = 0.1562
- Paired t-test (one-sided, greater): p = 0.0592

With n=5, the exact two-sided Wilcoxon floor when all gaps are positive is 1/16 = 0.0625; one-sided floor is 1/32 = 0.03125. Report the CI and the 5/5 positive-gap count alongside p-values.

## Per-subject gaps

| Subject | Informed | Random mean | Gap (pp) |
|---------|----------|-------------|----------|
| S1 | 94.39% | 94.55% | -0.16 |
| S2 | 88.10% | 87.04% | +1.05 |
| S3 | 89.35% | 88.76% | +0.59 |
| S4 | 88.07% | 87.08% | +0.99 |
| S5 | 87.39% | 87.39% | -0.00 |
