# Phase 3 — Measurement infrastructure

**Status: IN PROGRESS** (June 2026) — core bench **PASS** on board; energy + EMG pending.

**Prerequisite:** Phase 2 complete (`results/phase2/`).

## Pass criteria

| Check | Target | Status | Evidence |
|-------|--------|--------|----------|
| Single-window DMA latency (min/mean/max) | Phase 3 log | **PASS** | `board_bench.txt` — 7/7/7 µs |
| Batch throughput (200 windows) | windows/s, proto once | **PASS** | ~136k windows/s |
| PASS 200/200 batch golden | Batch outputs vs expect | **PASS** | `board_bench.txt` |
| PASS 200/200 per-window golden | Sequential DMA regression | **PASS** | `board_bench.txt` |
| Golden regression (optional) | Standalone golden app | pending | `board_golden.txt` |
| Energy (INA219 + shunt) | Static + dynamic over batch | **NOT YET MEASURED** | `energy_batch.txt` |

## Measured (ZedBoard, xc7z020 @ 100 MHz PL)

| Metric | Value |
|--------|-------|
| Single-window (min / mean / max) | 7 / 7 / 7 µs |
| Single-window throughput | ~143k windows/s |
| Batch 200 windows (total) | 1470 µs (~136k windows/s) |
| Batch golden | PASS 200/200 |
| Per-window golden | PASS 200/200 |

Batch uses **back-to-back single-window DMA** — see root README **Later fixes**.

## Run (board)

```bash
cd board/HDC_DMA
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
bash build_sw.sh
bash run_phase3_bench.sh
bash run_phase3_golden.sh     # optional
```

## Still pending

- EMG full-dataset replay (~0.5% vs Python)
- INA219 energy → `energy_batch.txt`
- SG DMA one-transfer batch (hardware follow-up)
