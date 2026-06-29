# Tier 4 comparison baselines (P-may2026)

Frozen EMG protocol; same train/test split as Hook A and board replay.

| Baseline | Spatial mean accuracy | On-board latency | Notes |
|----------|----------------------|------------------|-------|
| **ARM HDC (C, hdc_ref)** | **74.15%** | **819 µs**/window (mean) | 5 subjects; 200/200 golden on ZedBoard |
| **PL DMA batch** (reference) | **74.24%** | **~4 µs**/window | Phase 3 SG batch (~216k win/s) |
| Board RTL encoder | **74.24%** | — | ZedBoard EMG replay (reference) |
| MLP int8 (full, 5 subj) | **93.01%** float / **54.05%** int8 | — | ~5.8k params; 25 epochs; full TEST split |
| AXI-Lite PL path | — | ~3 µs/window | Phase 1 register-mapped baseline |

## ARM HDC — on-board timing (cross-compile)

```bash
bash scripts/build_arm_bench_cross.sh              # -> board/HDC_DMA/app/build/Final_HDC_arm_bench.elf
bash board/HDC_DMA/run_arm_bench.sh                # ZedBoard + JTAG (needs USB connected)
```

JTAG readback @ `0x00100400`, magic `0xBEC00006`. Compare to PL DMA batch (~4 µs/window).

- **Accuracy (host):** done — 74.15% ([`arm_hdc_results.json`](arm_hdc_results.json))
- **Timing (board):** done — **819 µs** mean encode+classify, **1221 win/s**, 200/200 golden
      ([`arm_hdc_board_timing.txt`](arm_hdc_board_timing.txt), 2026-06-29). ~**200× slower** than PL DMA batch (~4 µs/window).
- **Energy:** pending INA219 (needed for ~10× energy claim)

## MLP

- **Runner:** `python_ref/run_mlp_baseline.py`
- **Results:** [`mlp_results.json`](mlp_results.json) — full 5-subject run (2026-06-29)

| Subject | Float | Int8 |
|---------|-------|------|
| 1 | 95.83% | 49.18% |
| 2 | 92.34% | 56.50% |
| 3 | 94.52% | 55.54% |
| 4 | 90.53% | 53.25% |
| 5 | 91.83% | 55.79% |
| **Spatial mean** | **93.01%** | **54.05%** |

Architecture `4-100-50-5`, 5,805 params, 25 epochs, ~71 s wall time on VDI.
Int8 uses pre-train weight quantize today — fix before citing int8 in the paper.

## Regenerate

```bash
python3 python_ref/run_arm_hdc_baseline.py          # full (~2 min)
python3 python_ref/run_mlp_baseline.py              # full (~minutes)
python3 python_ref/run_baselines.py                 # both
```

Build host library: `bash scripts/build_hdc_arm_host.sh shared`  
Cross-compile board bench: `bash scripts/build_arm_bench_cross.sh`
