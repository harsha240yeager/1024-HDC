# Twist 1 — informed vs random pruning @ iso-density

Generated: 2026-07-19T13:43:59Z
Config: D=1024, CNT_W=6, keep=0.125 (128 bits)
Random seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]

## Headline (5-subject mean)

| Mask | Spatial mean accuracy |
|------|----------------------|
| Unpruned (keep=1.0) | **72.65%** |
| Fisher informed | **72.65%** |
| Random (mean ± std over seeds) | **65.75% ± 3.20 pp** |
| **Gap (informed − random)** | **+6.90 pp** |

Target ≥ 5 pp: **PASS**

## Per subject

| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |
|---------|----------|---------------|----------|----------|
| S1 | 76.90% | 70.36% | +6.54 | 76.90% |
| S2 | 70.03% | 58.71% | +11.32 | 70.03% |
| S3 | 80.98% | 71.17% | +9.81 | 80.98% |
| S4 | 63.05% | 61.26% | +1.79 | 63.05% |
| S5 | 72.28% | 67.23% | +5.05 | 72.28% |

## Regenerate

```bash
python3 python_ref/run_twist1_sweep.py --quick
python3 python_ref/run_twist1_sweep.py
python3 python_ref/plot_results.py
```
