# Twist 1 — informed vs random pruning @ iso-density

Generated: 2026-07-08T16:40:03Z
Config: D=1024, CNT_W=6, keep=0.5 (512 bits)
Random seeds: [0, 1, 2, 3, 4]

## Headline (5-subject mean)

| Mask | Spatial mean accuracy |
|------|----------------------|
| Unpruned (keep=1.0) | **74.15%** |
| Fisher informed | **74.15%** |
| Random (mean ± std over seeds) | **72.44% ± 1.57 pp** |
| **Gap (informed − random)** | **+1.70 pp** |

Target ≥ 5 pp: **FAIL (so far)**

## Per subject

| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |
|---------|----------|---------------|----------|----------|
| S1 | 78.53% | 76.90% | +1.63 | 78.53% |
| S2 | 71.32% | 67.73% | +3.59 | 71.32% |
| S3 | 82.26% | 81.14% | +1.12 | 82.26% |
| S4 | 64.21% | 64.07% | +0.14 | 64.21% |
| S5 | 74.41% | 72.37% | +2.05 | 74.41% |

## Regenerate

```bash
python3 python_ref/run_twist1_sweep.py --quick
python3 python_ref/run_twist1_sweep.py
python3 python_ref/plot_results.py
```
