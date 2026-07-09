# Twist 1 — informed vs random pruning @ iso-density

Generated: 2026-07-09T07:42:56Z
Config: D=1024, CNT_W=6, keep=0.125 (128 bits)
Random seeds: [0, 1, 2, 3, 4]

## Headline (5-subject mean)

| Mask | Spatial mean accuracy |
|------|----------------------|
| Unpruned (keep=1.0) | **74.15%** |
| Fisher informed | **74.15%** |
| Random (mean ± std over seeds) | **65.51% ± 2.85 pp** |
| **Gap (informed − random)** | **+8.63 pp** |

Target ≥ 5 pp: **PASS**

## Per subject

| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |
|---------|----------|---------------|----------|----------|
| S1 | 78.53% | 71.37% | +7.16 | 78.53% |
| S2 | 71.32% | 58.33% | +12.99 | 71.32% |
| S3 | 82.26% | 69.95% | +12.30 | 82.26% |
| S4 | 64.21% | 60.68% | +3.53 | 64.21% |
| S5 | 74.41% | 67.23% | +7.18 | 74.41% |

## Regenerate

```bash
python3 python_ref/run_twist1_sweep.py --quick
python3 python_ref/run_twist1_sweep.py
python3 python_ref/plot_results.py
```
