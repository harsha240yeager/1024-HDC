# Issue 9 — ranking baselines @ 128 bits

Generated: 2026-07-24T12:51:54Z
Protocol: **HDC-2** · Engine: **hdc_ref**
D=1024  keep=0.125 (128 bits)  item_mem_seeds=[42]  subjects=[1, 2, 3, 4, 5]
Test cap: 15000 random windows/subject

## Spatial mean (S1–S5)

| Method | Acc | Gap vs Fisher (pp) | Jaccard vs Fisher | Cost | Retrain? |
|--------|-----|--------------------|-------------------|------|----------|
| fisher | 72.58% | +0.00 | 1.000 | low | no |
| variance | 72.58% | +0.00 | 0.806 | low | no |
| mutual_information | 72.58% | +0.00 | 0.946 | medium | no |
| class_mean_separation | 72.58% | +0.00 | 0.907 | low | no |
| prototype_disagreement | 72.58% | +0.00 | 0.184 | low | no |
| entropy | 72.58% | +0.00 | 0.806 | low | no |
| random_active | 71.45% | -1.13 | 0.453 | low | no |
| random_full | 64.55% | -8.04 | 0.068 | low | no |

## Notes

- Informed methods rank TRAIN-encoded bits; random methods average 5 seeds.
- `random_active` samples only from positions that vary (#5 fair baseline).
- Learned mask omitted (optional / high cost).
- **Why informed methods tie:** with ~209 active bits and keep=128, Hook A is
  already flat — any ranking that prefers varying bits retains a lossless
  subset. Mask Jaccard vs Fisher still differs (0.18–0.95); accuracy does not.
  The paper claim is therefore *informed vs random*, not Fisher-unique.

## Regenerate

```bash
python3 python_ref/run_ranking_baselines.py --quick
python3 python_ref/run_ranking_baselines.py
```
