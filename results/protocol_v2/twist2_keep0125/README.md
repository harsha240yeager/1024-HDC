# Twist 2 — cross-subject Fisher mask transfer

Generated: 2026-07-20T16:05:08Z
Train subjects: [1, 2, 3]  ·  Test subjects: [4, 5]
Config: D=1024, CNT_W=6, keep=0.125 (128 bits)
Pooled TRAIN windows (mask source): 106379

## Headline (held-out test subjects, mean)

| Condition | Spatial mean accuracy |
|-----------|----------------------|
| Unpruned | **67.66%** |
| Local oracle (own-subject mask) | **67.66%** |
| Pooled transfer (train-subject mask) | **66.64%** |
| **Gap (local − pooled)** | **+1.02 pp** |

Target |gap| ≤ 3 pp: **GENERALISES**

## Per held-out subject

| Subject | Local oracle | Pooled transfer | Gap (pp) | Unpruned |
|---------|--------------|-----------------|----------|----------|
| S4 | 63.05% | 62.35% | +0.70 | 63.05% |
| S5 | 72.28% | 70.93% | +1.35 | 72.28% |

## Regenerate

```bash
python3 python_ref/run_twist2_sweep.py --quick
python3 python_ref/run_twist2_sweep.py
python3 python_ref/plot_results.py
```
