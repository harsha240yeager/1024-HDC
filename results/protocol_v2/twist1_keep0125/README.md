# Twist 1 — informed vs random pruning @ iso-density

Generated: 2026-07-18T09:19:33Z
Config: D=1024, CNT_W=6, keep=0.125 (128 bits)
Random seeds: [0, 1, 2, 3, 4]

## Headline (5-subject mean)

| Mask | Spatial mean accuracy |
|------|----------------------|
| Unpruned (keep=1.0) | **72.65%** |
| Fisher informed | **72.65%** |
| Random (mean ± std over seeds) | **64.71% ± 2.60 pp** |
| **Gap (informed − random)** | **+7.94 pp** |

Target ≥ 5 pp: **PASS**

## Per subject

| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |
|---------|----------|---------------|----------|----------|
| S1 | 76.90% | 69.35% | +7.55 | 76.90% |
| S2 | 70.03% | 57.93% | +12.10 | 70.03% |
| S3 | 80.98% | 69.81% | +11.16 | 80.98% |
| S4 | 63.05% | 60.22% | +2.83 | 63.05% |
| S5 | 72.28% | 66.23% | +6.05 | 72.28% |

## Regenerate

```bash
python3 python_ref/run_twist1_sweep.py --quick
python3 python_ref/run_twist1_sweep.py
python3 python_ref/plot_results.py
```
