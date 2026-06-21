# Phase 3 — Measurement infrastructure

**Status: IN PROGRESS** (June 2026) — batch throughput and E2E latency measured on board.

**Prerequisite:** Phase 2 complete (see `results/phase2/` — golden 200/200, ~7 µs/window).

Phase 3 turns the working DMA stream path into **publishable metrics**: sustained
throughput, end-to-end latency, full-dataset accuracy, and energy.

## Pass criteria

| Task | Target | Status | Evidence |
|------|--------|--------|----------|
| Stream batch bench | Sustained windows/s with proto loaded once | **PASS** | `board_batch_bench.txt` |
| End-to-end latency | Last input beat → result beat (global timer proxy) | **PASS** (proxy) | same file (`E2E proxy` section) |
| Full EMG dataset replay | Accuracy within ~0.5% of Python on real vectors | **PENDING** | `board_emg_replay.txt` |
| Energy (INA219 + shunt) | Static + dynamic mJ over fixed batch | **PENDING** | `energy_batch.txt` |

## Measured results (ZedBoard, xc7z020 @ 100 MHz PL)

| Metric | Phase 2 single-window | Phase 3 sustained batch (10 000 windows) |
|--------|----------------------|------------------------------------------|
| Mean latency | 7 µs | 7 µs/window |
| Throughput | ~143k windows/s | ~143k windows/s |
| E2E proxy (submit → both idle) | — | 6 µs mean (MM2S done @ 3 µs) |

Sustained throughput matches Phase 2 single-window bench — proto loaded once removes
only the config overhead (already amortized in Phase 2). True batch DMA (one MM2S
for N windows) needs SG DMA; current path is back-to-back single-window transfers.

## Measurement definitions

### Sustained batch throughput

- Load prototypes/mask **once** via config registers.
- Run `BATCH_WINDOWS` (default 10 000) **back-to-back** single-window DMA transfers.
- Report total time, mean µs/window, and windows/s.
- **Note:** AXI DMA simple mode asserts TLAST only on the final beat of each
  transfer. Multi-window TLAST mid-stream requires scatter-gather DMA (not in
  current BD). Batch = sequential `hdc_dma_stream_one()` calls, not one giant MM2S.

### End-to-end latency proxy

- `hdc_dma_stream_one_timed()` timestamps with the ARM global timer (`XTime_GetTime`).
- **E2E proxy:** ticks from both DMA directions submitted through both channels idle
  (MM2S done and S2MM complete). This approximates input launch → result in DDR.
- Future: PL counter from last input beat → first result beat (requires RTL hook).

### EMG dataset replay

1. Export windows: `python3 scripts/export_emg_board_vectors.py`
2. Rebuild `sw/hdc_emg_board_test.c` with generated `emg_board_vectors.h`
3. Run on board; compare class accuracy vs `python_ref` baseline

### Energy

See `energy_setup.md` and `energy_setup.txt` — INA219 on Vcc_int shunt, integrate
over a fixed batch while PS is idle (dynamic) and while holding reset (static).

## Software

| File | Role |
|------|------|
| `sw/hdc_dma_stream_batch_bench.c` | Sustained batch + E2E timed samples (primary Phase 3 app) |
| `sw/hdc_dma_stream_bench.c` | Phase 2 single-window latency + golden spot-check |
| `sw/hdc_dma_stream.c` | `hdc_dma_stream_one_timed()`, sequential batch |
| `sw/hdc_emg_board_test.c` | EMG replay scaffold |
| `scripts/export_emg_board_vectors.py` | Export EMG vectors for on-board replay |

## Run scripts

| Script | What it does |
|--------|--------------|
| `board/HDC_DMA/build_sw.sh` | Build golden, bench, batch ELFs (no Vivado) |
| `board/HDC_DMA/run_batch_bench.sh` | Program PL + batch bench + JTAG readback @ `0x00100200` |
| `board/HDC_DMA/run_golden_app.sh` | Phase 2 close-out: golden ELF @ `0x00100100` |
| `scripts/run_stream_bench_hdc.sh` | Legacy UART capture path (Final HDC workspace) |

DDR layout:

| Address | Magic | App |
|---------|-------|-----|
| `0x00100000` | `0xBEC00002` | Phase 2 latency bench |
| `0x00100100` | `0xBEC00003` | Phase 2 golden app |
| `0x00100200` | `0xBEC00004` | Phase 3 batch bench |
| `0x00100300` | `0xBEC00005` | Phase 3 EMG replay |

## Results files

| File | Description |
|------|-------------|
| `board_batch_bench.txt` | Sustained throughput + E2E latency |
| `board_emg_replay.txt` | Full-dataset accuracy (when wired) |
| `energy_batch.txt` | Static/dynamic energy over fixed batch |
| `energy_setup.txt` | Energy wiring notes (template) |
| `logs/` | Raw JTAG / measurement logs |

## Paper mapping (Hook A — Pareto)

| Axis | Phase 3 source |
|------|----------------|
| Accuracy | EMG replay vs Python |
| Throughput | Batch bench windows/s |
| Latency | E2E proxy (µs) |
| Energy | INA219 integration |
| Area | Phase 2 synthesis util (already recorded) |

Without EMG replay + energy, the Pareto plot is incomplete (throughput/latency done;
accuracy-on-EMG and energy remain).

## Next

Phase 4 — ARM-only HDC + tiny MLP baselines.  
Phase 5 — Hook A pruning sweep (runtime mask load, no resynthesis).
