# Issue #31 — Narrow vs baseline board evaluation

## Strong Paper 1 gate

- **LUT (integrated):** 35,206 → 10,601 (**−69.9%**) — PASS (≥10%)
- **Batch latency (200 windows):** 4 → 2 µs/w (**−50.0%**) — PASS (≥5%)
- **Overall gate (LUT or latency):** **PASS**

## Accuracy (493,512 windows, vs export ref)

| Anchor | Keep | Baseline PL | Narrow PL |
|--------|------|-------------|-----------|
| A | 1.0 | 72.78% | n/a (see note) |
| B | 0.5 | 72.78% | n/a (see note) |
| C | 0.125 | 72.84% | 72.84% |

Narrow bitstream implements **anchor C only** (baked K=128 gather). Anchors A/B use full-width baseline PL.

## Energy (INA219, anchor C, 200-window PL batch)

- Baseline PL: **11.98 ± 0.07** µJ/w
- Narrow PL: run `bash scripts/run_narrow_energy_campaign.sh` (ZedBoard + Pi INA219)

## Artifacts

| Item | Path |
|------|------|
| Narrow anchor C EMG | `anchors/anchor_C/board_emg_replay.txt` |
| Narrow latency bench | `board_bench.txt` |
| LUT (integrated) | `results/narrow_rtl/integrated_utilization_placed.rpt` |
| This summary | `board_eval_summary.json` |

