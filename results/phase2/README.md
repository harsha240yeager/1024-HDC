# Phase 2 — AXI-DMA + streaming inference

**Status: COMPLETE** (June 2026) — all pass criteria met on ZedBoard.

## Architecture

- `hdc_stream_system_bd_wrapper` replaces Phase 1 AXI-Lite inference wrapper
- AXI DMA (MM2S + S2MM, 32-bit, no SG) + HP0 to DDR
- Config @ `0x43C00000` (STAGING / LOAD_PROTO / LOAD_MASK)
- DMA lite @ `0x40400000`

## Pass criteria

| Check | Target | Status | Evidence |
|-------|--------|--------|----------|
| Synthesis / timing | WNS ≥ 0 @ 100 MHz, fits xc7z020 | **PASS** | `synthesis_timing.txt`, `synthesis_utilisation.txt` |
| Stream golden | 200/200 PASS via DMA | **PASS** | `board_golden.txt` |
| Functional | Same classes/distances as Phase 1 | **PASS** | Same `cosim_core` vectors (seed 42) |
| Throughput bench | vs Phase 1 ~3 µs/window baseline | **PASS** | `board_bench.txt` |

## Measured results (ZedBoard, xc7z020 @ 100 MHz PL)

| Metric | Phase 1 (AXI-Lite) | Phase 2 (DMA stream) |
|--------|--------------------|----------------------|
| Golden test | 200/200 PASS | 200/200 PASS |
| Latency (min / mean / max) | 3 / 3 / 3 µs | 7 / 7 / 8 µs |
| Peak throughput (1/mean) | ~333k windows/s | ~143k windows/s |
| WNS @ 100 MHz | +0.246 ns | +0.023 ns |
| Slice LUT util | ~59% | ~66% |

Phase 2 single-window latency is **~4 µs slower** than Phase 1 — expected from
DMA channel setup and CPU busy-wait on transfer completion (not yet batched).

## Two inference paths (paper roles)

| Path | Role | How verified |
|------|------|--------------|
| **Phase 1 — AXI-Lite** | Baseline #2: register-mapped; shows why streaming matters | `results/phase1/` |
| **Phase 2 — DMA stream** | Main inference path for throughput and energy | `results/phase2/` |

## How tests were run

| Test | Method | Script |
|------|--------|--------|
| Stream golden (200 cases) | Host-side JTAG drives config + DMA | `board/HDC_DMA/run_jtag.sh` |
| Latency bench (1000 iters + golden spot-check) | Bare-metal ELF + JTAG DDR readback @ `0x00100000` | `board/HDC_DMA/run_bench_load.tcl` (after `program_pl.tcl`) |

Bare-metal `sw/hdc_dma_stream_golden_test.c` is built and available via
`board/HDC_DMA/run_program.sh` (UART @ 115200); UART log not archived in repo
(JTAG golden is the primary verification on this setup).

## Software

| File | Role |
|------|------|
| `sw/hdc_dma_stream_golden_test.c` | 200-case DMA golden test (bare-metal) |
| `sw/hdc_dma_stream_bench.c` | Latency bench + golden spot-check |
| `sw/hdc_dma_stream.c` | DMA stream driver (with D-cache coherency) |
| `sw/hdc_core_regs.c` | Config load (proto/mask) |

Board workspace: `board/HDC_DMA/` (Vitis platform, ELFs, JTAG scripts).

## Results files

| File | Description |
|------|-------------|
| `board_golden.txt` | DMA golden — **PASS 200/200** (JTAG) |
| `board_bench.txt` | Latency bench — **PASS**, 7 µs mean, golden 200/200 |
| `synthesis_timing.txt` | WNS **+0.023 ns** @ 100 MHz |
| `synthesis_utilisation.txt` | 66% LUT, 96% slices |

## Optional close-out (not blocking Phase 3)

- [ ] UART capture log from `hdc_dma_stream_golden_test.c` → `board_golden_uart.txt`
- [ ] Archive raw JTAG logs from `/tmp/hdc_dma_jtag/` into this folder

## Next: Phase 3

See root `README.md` — batch DMA throughput, beat-accurate latency, full EMG
dataset replay on board, and energy measurement (INA219). Results → `results/phase3/`.
