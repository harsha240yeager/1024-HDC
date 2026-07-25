# Twist 2 — cross-subject Fisher mask transfer

Generated: 2026-07-24T15:05:37Z
Train subjects: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]  ·  Test subjects: [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]
Config: D=1024, CNT_W=6, keep=0.25 (256 bits)
Pooled TRAIN windows (mask source): 512487

## Headline (held-out test subjects, mean)

| Condition | Spatial mean accuracy |
|-----------|----------------------|
| Unpruned | **59.87%** |
| Local oracle (own-subject mask) | **59.87%** |
| Pooled transfer (train-subject mask) | **59.87%** |
| **Gap (local − pooled)** | **+0.00 pp** |

Target |gap| ≤ 3 pp: **GENERALISES**

## Per held-out subject

| Subject | Local oracle | Pooled transfer | Gap (pp) | Unpruned |
|---------|--------------|-----------------|----------|----------|
| S19 | 36.94% | 36.94% | +0.00 | 36.94% |
| S20 | 68.39% | 68.39% | +0.00 | 68.39% |
| S21 | 59.98% | 59.98% | +0.00 | 59.98% |
| S22 | 40.10% | 40.10% | +0.00 | 40.10% |
| S23 | 69.30% | 69.30% | +0.00 | 69.30% |
| S24 | 54.91% | 54.91% | +0.00 | 54.91% |
| S25 | 70.18% | 70.18% | +0.00 | 70.18% |
| S26 | 59.17% | 59.17% | +0.00 | 59.17% |
| S27 | 64.45% | 64.45% | +0.00 | 64.45% |
| S28 | 61.71% | 61.71% | +0.00 | 61.71% |
| S29 | 65.13% | 65.13% | +0.00 | 65.13% |
| S30 | 54.45% | 54.45% | +0.00 | 54.45% |
| S31 | 61.93% | 61.93% | +0.00 | 61.93% |
| S32 | 52.83% | 52.83% | +0.00 | 52.83% |
| S33 | 60.64% | 60.64% | +0.00 | 60.64% |
| S34 | 73.18% | 73.18% | +0.00 | 73.18% |
| S35 | 56.23% | 56.23% | +0.00 | 56.23% |
| S36 | 68.21% | 68.21% | +0.00 | 68.21% |

## Regenerate

```bash
python3 python_ref/run_twist2_sweep.py --quick
python3 python_ref/run_twist2_sweep.py
python3 python_ref/plot_results.py
```
