# Twist 1 — Stage B informed vs random @ iso-density (HDC-2)

Generated: 2026-07-28T12:03:21Z
Engine: **Stage B BSC** (4-channel spatial records, D=1024)
Protocol: **HDC-2** · keep=0.125 (128 bits)
Random seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]

## Headline (5-subject mean)

| Mask | Spatial mean accuracy |
|------|----------------------|
| Unpruned (keep=1.0) | **89.46%** |
| Fisher informed | **89.01%** |
| Random (mean ± std over seeds) | **86.19% ± 3.63 pp** |
| **Gap (informed − random)** | **+2.82 pp** |

Target ≥ 5 pp: **FAIL**

Compare hdc_ref Twist 1 @ same keep: **+6.90 pp** ([`twist1_keep0125_30seed/`](../twist1_keep0125_30seed/))

## Per subject

| Subject | Informed | Random (mean) | Gap (pp) | Unpruned |
|---------|----------|---------------|----------|----------|
| S1 | 93.34% | 91.21% | +2.13 | 94.39% |
| S2 | 87.16% | 81.14% | +6.02 | 88.10% |
| S3 | 92.48% | 87.80% | +4.68 | 89.35% |
| S4 | 87.54% | 84.40% | +3.13 | 88.07% |
| S5 | 84.53% | 86.41% | -1.87 | 87.39% |

## Regenerate

```bash
python3 python_ref/run_twist1_stage_b_sweep.py --quick
python3 python_ref/run_twist1_stage_b_sweep.py
```

Stage B baseline: [`stage_b_hdc2/`](../stage_b_hdc2/)
