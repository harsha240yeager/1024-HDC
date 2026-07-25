# Twist 2 @ 36 UCI subjects — HDC-2 keep-ratio stress grid

Train pooled Fisher mask on **S1–18 TRAIN** windows; evaluate local oracle vs pooled
transfer on **S19–36 TEST** (Protocol HDC-2, disjoint split).

Generated: 2026-07-24 · issue [#2](https://github.com/harsha240yeager/1024-HDC/issues/2)

## Headline (held-out test mean)

| Keep bits | Local oracle | Pooled transfer | Gap (local − pooled) | Generalises (≤3 pp)? |
|-----------|-------------|-----------------|----------------------|----------------------|
| 32 | 60.91% | 63.50% | **−2.59 pp** | Yes |
| 64 | 59.87% | 59.87% | 0.00 pp | Yes |
| 96 | 59.87% | 59.87% | 0.00 pp | Yes |
| 128 | 59.87% | 59.87% | 0.00 pp | Yes |
| 192 | 59.87% | 59.87% | 0.00 pp | Yes |
| 256 | 59.87% | 59.87% | 0.00 pp | Yes |

Unpruned baseline: **59.87%** (all keep points).

At **32 bits**, pooled cross-subject transfer **outperforms** local oracle by 2.59 pp
(still within the ≤3 pp generalisation target). At **64+ bits**, masks are lossless
(local = pooled = unpruned).

## Primary encode run

Full encode + eval @ keep=128: [`../twist2_36_v2_keep128/`](../twist2_36_v2_keep128/)

Grid points 32–256 reused that encode cache (`--evaluate-only`).

## Regenerate

```bash
bash scripts/run_twist2_36_v2_keep_grid.sh
bash scripts/run_twist2_36_v2_keep_grid.sh --keep-bits 32
```

See [`docs/TWIST2_36_REPRO.md`](../../../docs/TWIST2_36_REPRO.md).
