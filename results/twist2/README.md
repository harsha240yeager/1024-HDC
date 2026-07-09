# Twist 2 — cross-subject Fisher mask transfer

Generated: 2026-07-09T18:30:02Z
Train subjects: [1, 2, 3]  ·  Test subjects: [4, 5]
Config: D=1024, CNT_W=6, keep=0.125 (128 bits)
Pooled TRAIN windows (mask source): 106379

## Headline (held-out test subjects, mean)

| Condition | Spatial mean accuracy |
|-----------|----------------------|
| Unpruned | **69.31%** |
| Local oracle (own-subject mask) | **69.31%** |
| Pooled transfer (train-subject mask) | **68.45%** |
| **Gap (local − pooled)** | **+0.86 pp** |

Target |gap| ≤ 3 pp: **GENERALISES**

## Per held-out subject

| Subject | Local oracle | Pooled transfer | Gap (pp) | Unpruned |
|---------|--------------|-----------------|----------|----------|
| S4 | 64.21% | 63.58% | +0.63 | 64.21% |
| S5 | 74.41% | 73.33% | +1.09 | 74.41% |

## Regenerate

```bash
python3 python_ref/run_twist2_sweep.py --quick
python3 python_ref/run_twist2_sweep.py
python3 python_ref/plot_results.py
```
