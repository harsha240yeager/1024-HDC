# Twist 2 — cross-subject Fisher mask transfer

Generated: 2026-07-13T06:42:07Z
Train subjects: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]  ·  Test subjects: [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]
Config: D=1024, CNT_W=6, keep=0.125 (128 bits)
Pooled TRAIN windows (mask source): 512487

## Headline (held-out test subjects, mean)

| Condition | Spatial mean accuracy |
|-----------|----------------------|
| Unpruned | **60.74%** |
| Local oracle (own-subject mask) | **60.74%** |
| Pooled transfer (train-subject mask) | **60.74%** |
| **Gap (local − pooled)** | **+0.00 pp** |

Target |gap| ≤ 3 pp: **GENERALISES**

## Per held-out subject

| Subject | Local oracle | Pooled transfer | Gap (pp) | Unpruned |
|---------|--------------|-----------------|----------|----------|
| S19 | 38.05% | 38.05% | +0.00 | 38.05% |
| S20 | 69.89% | 69.89% | +0.00 | 69.89% |
| S21 | 61.84% | 61.84% | +0.00 | 61.84% |
| S22 | 42.24% | 42.24% | +0.00 | 42.24% |
| S23 | 69.37% | 69.37% | +0.00 | 69.37% |
| S24 | 54.59% | 54.59% | +0.00 | 54.59% |
| S25 | 71.05% | 71.05% | +0.00 | 71.05% |
| S26 | 61.01% | 61.01% | +0.00 | 61.01% |
| S27 | 65.19% | 65.19% | +0.00 | 65.19% |
| S28 | 63.60% | 63.60% | +0.00 | 63.60% |
| S29 | 66.41% | 66.41% | +0.00 | 66.41% |
| S30 | 54.54% | 54.54% | +0.00 | 54.54% |
| S31 | 61.88% | 61.88% | +0.00 | 61.88% |
| S32 | 53.97% | 53.97% | +0.00 | 53.97% |
| S33 | 61.47% | 61.47% | +0.00 | 61.47% |
| S34 | 72.62% | 72.62% | +0.00 | 72.62% |
| S35 | 57.43% | 57.43% | +0.00 | 57.43% |
| S36 | 68.19% | 68.19% | +0.00 | 68.19% |

## Regenerate

```bash
python3 python_ref/run_twist2_sweep.py --quick
python3 python_ref/run_twist2_sweep.py
python3 python_ref/plot_results.py
```
