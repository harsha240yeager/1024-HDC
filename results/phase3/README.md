# Phase 3 — Measurement infrastructure

**Batch bench: COMPLETE** (June 2026, SG DMA + timing-clean bitstream)  
**Full Phase 3 (paper): IN PROGRESS** — EMG v1 RTL parity done; v2 full replay + energy pending

**Prerequisite:** Phase 2 complete (`results/phase2/`).

## Close checklist — batch measurement (minimum)

| # | Task | Status |
|---|------|--------|
| 1 | Rebuild bench ELF (`Final_HDC_dma_bench.elf`) | **DONE** — `board/HDC_DMA/build_sw.sh` |
| 2 | Program timing-clean bitstream (physopt) | **DONE** — `design_1_wrapper.bit` @ June 2026 |
| 3 | Run bench on board | **DONE** — JTAG readback (`run_phase3_bench.sh`) |
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
| Single-window latency (min/mean/max) | **PASS** | 58 / 58 / 59 µs |
| Batch throughput (200 windows) | **PASS** | ~216k windows/s (SG batch) |
| PASS 200/200 batch golden | **PASS** | `board_bench.txt` |
| PASS 200/200 per-window golden | **PASS** | `board_bench.txt` |
| Implementation timing @ 100 MHz | **PASS** | WNS +0.111 ns (physopt) |
| Synthesis critical warnings | **PASS** | 0 (OOC `.mem` staging) |

## Measured (ZedBoard, xc7z020 @ 100 MHz PL)

| Metric | Value |
|--------|-------|
| Single-window (min / mean / max) | 58 / 58 / 59 µs |
| Single-window throughput | ~17k windows/s |
| Batch 200 windows (total) | 926 µs (~216k windows/s) |
| Batch mean/window | ~4 µs |
| Batch golden | PASS 200/200 |
| Per-window golden | PASS 200/200 |
| Prior sequential fallback | ~136k windows/s (pre-SG bitstream) |

Batch = **scatter-gather DMA** with one MM2S/S2MM descriptor ring (200 windows),
input beat FIFO in `hdc_stream_wrapper.sv`, BSP `XPAR_AXI_DMA_0_INCLUDE_SG 1`.

## Implementation / timing

| Stage | WNS | Notes |
|-------|-----|-------|
| Route only (`impl_1` default in GUI) | -0.049 ns | 1 failing endpoint — stale project view |
| Post-route physopt (shipped bitstream) | **+0.111 ns** | 0 failing endpoints |

Authoritative checkpoint: `design_1_wrapper_routed_physopt.dcp`  
Report: `design_1_wrapper_timing_summary_physopt.rpt` (in Vivado project tree)

## JTAG reliability (ZedBoard)

Board runs use JTAG DDR readback (`run_phase3_bench.sh`), not UART. On this setup:

- PL programming may fail on attempt 1 (`ftdi_*`, `could not find configuration request`) — **retry**.
- JTAG target timeout on first connect — **retry** after a few seconds.
- Garbage DDR magic (e.g. `0xEA000049`) means session failed — close minicom/Vitis debug and retry.

Successful run: 2026-06-22 — log in `logs/board_bench_run.log`.

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

Full Vivado rebuild + bench:

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
bash scripts/full_rebuild_and_bench.sh
```

## Full Phase 3 close (paper) — still pending

| # | Task | Output | Status |
|---|------|--------|--------|
| 6 | Energy (INA219 + shunt on Vcc_int) | `energy_batch.txt` + fill `energy_setup.txt` | **NOT DONE** — hardware pending |
| 7a | EMG v1 RTL parity (500 windows, subject 1) | `board_emg_replay.txt` | **DONE** — board 59.60% == export 59.60% |
| 7b | EMG v2 full TEST-split replay | `board_emg_replay.txt` | **PENDING** — export + board run |

Scaffolds wired: `scripts/export_emg_board_vectors.py` (v2), `sw/hdc_emg_board_test.c`, `run_phase3_emg.sh`.

### EMG replay pass criteria (v1 vs v2)

| | v1 (superseded) | v2 (current) |
|---|-----------------|--------------|
| Export scope | 500 random windows, subject 1 | TEST split, all subjects (config order) |
| Export ref engine | hdc_ref only | `--engine hdc_ref` (default) or `stage_b_bsc` |
| Board PASS | vs frozen 90.30% baseline | \|board − export ref\| ≤ 0.5% |
| Frozen baseline | PASS/FAIL gate | INFO only when `--engine stage_b_bsc` |
| v1 result | **DONE** — board 59.60% == export 59.60% (RTL verified) | — |

```bash
# v2 export (RTL-matched ref, default)
bash scripts/prep_emg_board_test.sh
# dev subset
EMG_MAX_WINDOWS=2000 bash scripts/prep_emg_board_test.sh
cd board/HDC_DMA && bash build_sw.sh && bash run_phase3_emg.sh
```

## Results files

| File | Description |
|------|-------------|
| `board_bench.txt` | **Primary** — batch measurement close-out (June 2026) |
| `board_golden.txt` | Optional golden regression |
| `board_batch_bench.txt` | Supplementary 10k sequential bench |
| `board_emg_replay.txt` | EMG — v1 RTL parity **done**; v2 full replay pending |
| `logs/board_emg_replay_v1.log` | Raw v1 board run log |
| `energy_batch.txt` | *(template)* until INA219 measured |
| `energy_setup.txt` | Wiring / procedure notes |
| `logs/` | Raw JTAG logs |
