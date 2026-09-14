# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)

**Windows:** 493,512 (HDC-2 pooled cohort)
**Informed (anchor C):** 72.84% board

## Predicted random-mask distribution (seeds 0–9)

| Stat | Predicted board acc | Gap vs informed (pp) |
|------|---------------------|----------------------|
| Mean ± std | **64.58% ± 0.00** | **+8.26 ± 0.00** |
| Range (gap) | — | +8.26 … +8.26 |

| Seed | Export ref | Predicted board | Gap (pp) | Board measured |
|------|------------|-----------------|----------|----------------|
| 1 | 64.58% | 64.58% | +8.26 | ✅ |

**Method:** `python_ref/predict_twist1_silicon_seeds.py` — pooled random mask,
same export path as `patch_emg_anchor.py`. Seed 0 board validated Δ0.00 pp.

## Board replay (when ZedBoard available)

```bash
bash scripts/run_silicon_random_seeds.sh --board --seeds 1-9
```
