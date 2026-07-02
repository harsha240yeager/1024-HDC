# Phase 3 energy measurement runs (PL batch, J21 + INA219)

**Integration:** `batch` mode in `scripts/ina219_log.py` (default) — scales by
`batch_duration_ms` from `board_bench.txt`, not the full 30 s log.

| Run | Static (mW) | Total (µJ/w) | Dynamic (µJ/w) | Bench µs |
|-----|-------------|--------------|----------------|----------|
| 1 | 2561.3 | 11.86 | 0.048 | 926 |
| 2 | 2562.4 | 11.86 | 0.439 | 926 |
| 3 | 2543.9 | 11.96 | 0.011 | 940 |

**Mean ± std (n=3):** static **2556 ± 8 mW**; total **11.89 ± 0.04 µJ/window**

See [`../energy_summary.txt`](../energy_summary.txt).
