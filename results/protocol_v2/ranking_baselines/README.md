# Issue 9 — ranking baselines @ 128 bits

Generated: 2026-09-17T20:17:19Z
Protocol: **HDC-2** · Engine: **hdc_ref**
D=1024  keep=0.125 (128 bits)  item_mem_seeds=[42]  subjects=[1, 2, 3, 4, 5]
Test cap: all random windows/subject

## Spatial mean (S1–S5)

| Method | Acc | Gap vs Fisher (pp) | Jaccard vs Fisher | Cost | Retrain? |
|--------|-----|--------------------|-------------------|------|----------|
| fisher | 72.65% | +0.00 | 1.000 | low | no |
| variance | 72.65% | +0.00 | 0.806 | low | no |
| mutual_information | 72.65% | +0.00 | 0.946 | medium | no |
| class_mean_separation | 72.65% | +0.00 | 0.907 | low | no |
| prototype_disagreement | 72.65% | +0.00 | 0.184 | low | no |
| entropy | 72.65% | +0.00 | 0.806 | low | no |
| random_active | 71.61% | -1.04 | 0.454 | low | no |
| random_full | 64.71% | -7.94 | 0.068 | low | no |

## Notes

- Informed methods rank TRAIN-encoded bits; random methods average 5 seeds.
- `random_active` samples only from positions that vary (#5 fair baseline).
- Learned mask omitted (optional / high cost).

## Regenerate

```bash
python3 python_ref/run_ranking_baselines.py --quick
python3 python_ref/run_ranking_baselines.py
```
