# Phase 3 — Measurement infrastructure

**Batch bench: COMPLETE** (June 2026)  
**Full Phase 3 (paper): IN PROGRESS** — energy + EMG pending

**Prerequisite:** Phase 2 complete (`results/phase2/`).

## Close checklist — batch measurement (minimum)

| # | Task | Status |
|---|------|--------|
| 1 | Rebuild bench ELF (`Final_HDC_dma_bench.elf`) | **DONE** — `board/HDC_DMA/build_sw.sh` |
| 2 | Program Phase 2 bitstream | **DONE** — same `design_1_wrapper` as phase2 |
| 3 | Run bench on board | **DONE** — JTAG readback (`run_phase3_bench.sh`); UART optional |
| 4 | Verify pass lines in log | **DONE** — see `board_bench.txt` |
| 5 | Save + commit `board_bench.txt` | **DONE** |

### Pass lines (required)

```
--- Single-window DMA latency ---
min  = ... us
mean = ... us
max  = ... us
--- Batch DMA throughput ---
throughput ~ XXXXX windows/s (batch / total)
--- Golden batch check (batch DMA outputs) ---
PASS: 200/200 batch golden cases
--- Golden batch check (per-window DMA) ---
PASS: 200/200 stream golden cases
```

## Pass criteria

| Check | Status | Evidence |
|-------|--------|----------|
| Single-window latency (min/mean/max) | **PASS** | 7 / 7 / 7 µs |
| Batch throughput (200 windows) | **PASS** | ~136k windows/s |
| PASS 200/200 batch golden | **PASS** | `board_bench.txt` |
| PASS 200/200 per-window golden | **PASS** | `board_bench.txt` |
| Golden regression (optional) | **PASS** | `board_golden.txt` |

## Measured (ZedBoard, xc7z020 @ 100 MHz PL)

| Metric | Value |
|--------|-------|
| Single-window (min / mean / max) | 7 / 7 / 7 µs |
| Single-window throughput | ~143k windows/s |
| Batch 200 windows (total) | 1470 µs (~136k windows/s) |
| Batch golden | PASS 200/200 |
| Per-window golden | PASS 200/200 |

Batch = **200 back-to-back single-window DMA** transfers (proto loaded once).
True one-MM2S batch needs SG DMA — root `README.md` **Later fixes**.

## Run on VDI

```bash
cd ~/1024-HDC
git pull
bash scripts/prep_golden_test.sh
cd board/HDC_DMA
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
bash build_sw.sh
bash run_phase3_bench.sh    # JTAG → results/phase3/board_bench.txt
```

Alternative (UART capture, if serial available and JTAG idle):

```bash
bash scripts/build_hdc_dma_stream_bench.sh   # needs HDC_BSP paths
bash scripts/run_stream_bench_hdc.sh
```

## Full Phase 3 close (paper) — still pending

| # | Task | Output | Status |
|---|------|--------|--------|
| 6 | Energy (INA219 + shunt on Vcc_int) | `energy_batch.txt` + fill `energy_setup.txt` | **NOT DONE** — hardware pending |
| 7 | Full EMG replay on board | `board_emg_replay.txt` | **NOT DONE** — export vectors + wire `hdc_emg_board_test.c` |

Scaffolds: `scripts/ina219_log.py`, `scripts/export_emg_board_vectors.py`, `sw/hdc_emg_board_test.c`.

## Results files

| File | Description |
|------|-------------|
| `board_bench.txt` | **Primary** — batch measurement close-out |
| `board_golden.txt` | Optional golden regression |
| `board_batch_bench.txt` | Supplementary 10k sequential bench |
| `board_emg_replay.txt` | *(not yet)* EMG accuracy vs Python |
| `energy_batch.txt` | *(template)* until INA219 measured |
| `energy_setup.txt` | Wiring / procedure notes |
| `logs/` | Raw JTAG logs |
