# Phase 3 — Measurement infrastructure

**Prerequisite:** Phase 2 complete (see `results/phase2/` — golden 200/200, ~7 µs/window).

Phase 3 turns a working DMA stream path into **publishable metrics**: latency,
batch throughput, and (next) energy. Software is in the repo; board runs fill
the files below.

## Software

| App | Purpose |
|-----|---------|
| `sw/hdc_dma_stream_bench.c` | Single-window latency + batch throughput + golden verify |
| `sw/hdc_dma_stream_golden_test.c` | Phase 2 correctness (run first if bitstream is new) |

### Build (VDI)

```bash
bash scripts/prep_golden_test.sh
bash scripts/build_hdc_dma_stream_bench.sh
```

Vitis alternative: new app with sources above + `xaxidma` + `xiltimer` in BSP.

### Run

Program Phase 2 bitstream, run `hdc_dma_stream_bench.elf`, UART **115200**.

Or capture via script (when ELF is in Final HDC workspace):

```bash
bash scripts/run_stream_bench_hdc.sh
```

## What the bench measures

| Section | Metric | Compare to |
|---------|--------|------------|
| Single-window DMA | min / mean / max µs per window | Phase 1 AXI-Lite (~3 µs) |
| Batch DMA | total µs for N windows, windows/s | Phase 1 peak ~333k/s |
| Golden batch | 200/200 on batch outputs | Phase 2 per-window golden |

**Batch mode:** one MM2S of `N×3` words + one S2MM of `N×1` words. The stream
wrapper accepts input only in `ST_IN`; DMA naturally paces windows via `tready`.

**JTAG readback:** results published at **`0x00100100`**, magic **`0xBEC00003`**.

## Files to update after each run

| File | Contents |
|------|----------|
| `board_bench.txt` | Full UART log from `hdc_dma_stream_bench` |
| `board_golden.txt` | Optional re-run of Phase 2 golden for regression |
| `energy_setup.txt` | Bench wiring notes (when INA219 is connected) |
| `energy_batch.txt` | mJ per inference batch (after shunt measurement) |

## Pass criteria

- [ ] Single-window DMA latency reported (min/mean/max)
- [ ] Batch throughput reported for 200 windows
- [ ] `PASS: 200/200` on batch golden outputs
- [ ] Results saved under `results/phase3/`
- [ ] Energy measurement (optional Phase 3b — see `energy_setup.txt`)

## Next after Phase 3

Phase 4 — ARM-only HDC + tiny MLP baselines.  
Phase 5 — Hook A pruning sweep (runtime mask load, no resynthesis).
