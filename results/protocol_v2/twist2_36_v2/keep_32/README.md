# Twist 2 — cross-subject Fisher mask transfer

Generated: 2026-07-24T14:49:28Z
Train subjects: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]  ·  Test subjects: [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]
Config: D=1024, CNT_W=6, keep=0.03125 (32 bits)
Pooled TRAIN windows (mask source): 512487

## Headline (held-out test subjects, mean)

| Condition | Spatial mean accuracy |
|-----------|----------------------|
| Unpruned | **59.87%** |
| Local oracle (own-subject mask) | **60.91%** |
| Pooled transfer (train-subject mask) | **63.50%** |
| **Gap (local − pooled)** | **-2.59 pp** |

Target |gap| ≤ 3 pp: **GENERALISES**

## Per held-out subject

| Subject | Local oracle | Pooled transfer | Gap (pp) | Unpruned |
|---------|--------------|-----------------|----------|----------|
| S19 | 64.17% | 55.32% | +8.85 | 36.94% |
| S20 | 68.39% | 68.39% | +0.00 | 68.39% |
| S21 | 52.93% | 52.93% | +0.00 | 59.98% |
| S22 | 40.10% | 63.81% | -23.71 | 40.10% |
| S23 | 69.30% | 65.92% | +3.38 | 69.30% |
| S24 | 54.91% | 73.01% | -18.11 | 54.91% |
| S25 | 70.18% | 70.18% | +0.00 | 70.18% |
| S26 | 59.17% | 59.17% | +0.00 | 59.17% |
| S27 | 64.45% | 71.22% | -6.78 | 64.45% |
| S28 | 61.71% | 61.71% | +0.00 | 61.71% |
| S29 | 65.13% | 60.02% | +5.11 | 65.13% |
| S30 | 54.45% | 54.15% | +0.30 | 54.45% |
| S31 | 60.44% | 60.44% | +0.00 | 61.93% |
| S32 | 52.83% | 64.48% | -11.65 | 52.83% |
| S33 | 60.64% | 58.44% | +2.20 | 60.64% |
| S34 | 73.18% | 72.10% | +1.08 | 73.18% |
| S35 | 56.23% | 63.37% | -7.14 | 56.23% |
| S36 | 68.21% | 68.43% | -0.23 | 68.21% |

## Regenerate

```bash
python3 python_ref/run_twist2_sweep.py --quick
python3 python_ref/run_twist2_sweep.py
python3 python_ref/plot_results.py
```
