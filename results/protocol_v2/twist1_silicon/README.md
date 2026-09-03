# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)

**Windows:** 493,512 (HDC-2 pooled cohort)
**Informed (anchor C):** 72.84% board

## Predicted random-mask distribution (seeds 0–9)

| Stat | Predicted board acc | Gap vs informed (pp) |
|------|---------------------|----------------------|
| Mean ± std | **65.40% ± 2.59** | **+7.44 ± 2.59** |
| Range (gap) | — | +3.61 … +11.29 |

| Seed | Export ref | Predicted board | Gap (pp) | Board measured |
|------|------------|-----------------|----------|----------------|
| 0 | 62.51% | 62.51% | +10.33 | ✅ |
| 1 | 64.58% | 64.58% | +8.26 | ⏳ |
| 2 | 67.64% | 67.64% | +5.20 | ⏳ |
| 3 | 62.78% | 62.78% | +10.06 | ⏳ |
| 4 | 66.00% | 66.00% | +6.84 | ⏳ |
| 5 | 61.55% | 61.55% | +11.29 | ⏳ |
| 6 | 64.63% | 64.63% | +8.21 | ⏳ |
| 7 | 67.57% | 67.57% | +5.27 | ⏳ |
| 8 | 69.23% | 69.23% | +3.61 | ⏳ |
| 9 | 67.49% | 67.49% | +5.35 | ⏳ |

**Method:** `python_ref/predict_twist1_silicon_seeds.py` — pooled random mask,
same export path as `patch_emg_anchor.py`. Seed 0 board validated Δ0.00 pp.

## Board replay (when ZedBoard available)

```bash
bash scripts/run_silicon_random_seeds.sh --board --seeds 1-9
```
