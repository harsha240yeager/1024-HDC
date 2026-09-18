# Issue 39 — Antonio identical-across-prototypes compact baseline

Generated: 2026-09-17T23:09:35Z
Protocol: **HDC-2**
D=1024  Fisher keep=0.125 (128 bits)
Subjects: [1, 2, 3, 4, 5]
Test cap: all windows/subject

## Summary (spatial mean over S1–S5)

| Engine | Full | Antonio | Fisher-128 | Random@128 (active) | n_keep Antonio | J(A,F) | Δ Antonio−Fisher (pp) |
|--------|------|---------|------------|---------------------|----------------|--------|----------------------|
| hdc_ref | 72.65% | 72.65% | 72.65% | 71.61% | 27 | 0.208 | +0.00 |
| stage_b | 89.46% | 89.46% | 89.01% | 88.62% | 203 | 0.661 | +0.45 |

## Method

- **Antonio:** mask = bits where class TRAIN prototypes are *not* all identical.
- **Fisher-128:** top 128 TRAIN Fisher scores (same density as paper).
- **Random@128:** uniform on active support, averaged over random seeds.

## Regenerate

```bash
python3 python_ref/run_antonio_compact_baseline.py --quick
python3 python_ref/run_antonio_compact_baseline.py
```
