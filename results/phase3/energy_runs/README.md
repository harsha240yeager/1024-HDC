# Phase 3 energy measurement runs (INA219 + J21)

**Integration:** `batch` mode in `scripts/ina219_log.py` — scales by measured
`batch_duration_ms` (PL ~0.93 ms / 200 windows; ARM ~164 ms / 200 windows).

**Mask:** pooled Fisher-informed, same bytes in `sw/golden_vectors.h` and
`sw/emg_board_vectors.h` per anchor.

## Per-anchor results (n=3 each, 2026-07-02)

| Anchor | keep | Static (mW) | Total (µJ/w) | Directory |
|--------|------|-------------|--------------|-----------|
| A | 1.0 | 2586 ± 17 | 11.98 ± 0.07 | [`anchor_A/`](anchor_A/README.md) |
| B | 0.5 | 2570 ± 8 | 11.90 ± 0.04 | [`anchor_B/`](anchor_B/README.md) |
| C | 0.125 | 2551 ± 25 | 11.81 ± 0.12 | [`anchor_C/`](anchor_C/README.md) |
| ARM | 1.0 | 2553 ± 8 | 2088 ± 6 | [`anchor_ARM/`](anchor_ARM/README.md) |

Aggregate: [`../energy_summary.txt`](../energy_summary.txt).

## Legacy

| Directory | Note |
|-----------|------|
| `run01/`–`run03/` | First PL campaign (cosim `golden_mask`); superseded by `anchor_A/` |

Raw INA219 CSVs stay local on the Pi (not in git).

## Scripts

```bash
bash scripts/run_energy_only.sh              # full campaign
bash scripts/run_after_energy_review.sh      # golden_expect + EMG anchors
```
