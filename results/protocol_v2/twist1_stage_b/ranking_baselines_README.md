# Issue 22 — Stage B ranking baselines @ 128 bits

Generated: 2026-07-28T12:37:51Z
Protocol: **HDC-2** · Engine: **stage_b_bsc**
D=1024  keep=0.125 (128 bits)  item_mem_seed=1  subjects=[1, 2, 3, 4, 5]
Mean active bit support: **335** / 1024

## Spatial mean (S1–S5)

| Method | Acc | Gap vs Fisher (pp) | Jaccard vs Fisher | Pred agree vs Fisher | Cost |
|--------|-----|--------------------|-------------------|----------------------|------|
| mutual_information | 92.77% | +2.29 | 0.713 | 94.03% | medium |
| class_mean_separation | 92.40% | +1.92 | 0.755 | 94.93% | low |
| variance | 91.76% | +1.28 | 0.558 | 91.69% | low |
| entropy | 91.76% | +1.28 | 0.558 | 91.69% | low |
| fisher | 90.48% | +0.00 | 1.000 | 100.00% | low |
| prototype_disagreement | 89.91% | -0.56 | 0.586 | 93.37% | low |
| random_active | 88.72% | -1.76 | 0.238 | 90.77% | low |
| random_full | 83.75% | -6.73 | 0.063 | 83.97% | low |

**Jaccard vs Fisher (informed methods, excl. Fisher):** 0.558 – 0.755

## Dense-support conclusion (Sec. V-D extension)

On the **Stage B** encoder (~91.3% unpruned, ~335 active bits), informed ranking criteria **separate in accuracy** at keep=128 (max |gap| vs Fisher = 2.29 pp). Mask Jaccard vs Fisher spans **0.56–0.75**. Dense support changes which criterion wins at fixed K — contrast with hdc_ref where all informed methods tied.

Compare sparse encoder: [`ranking_baselines/`](../ranking_baselines/) (issue #9).
Stage B iso-density: [`README.md`](README.md) (issue #21).

## Regenerate

```bash
python3 python_ref/run_ranking_baselines_stage_b.py --quick
python3 python_ref/run_ranking_baselines_stage_b.py
```
