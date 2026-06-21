# Phase 2 — AXI-DMA + streaming inference

**Status:** Golden test **PASS** on board; throughput bench scaffolded (board run pending).

## Architecture

- `hdc_stream_system_bd_wrapper` replaces Phase 1 AXI-Lite inference wrapper
- AXI DMA (MM2S + S2MM, 32-bit, no SG) + HP0 to DDR
- Config @ `0x43C00000` (STAGING / LOAD_PROTO / LOAD_MASK)
- DMA lite @ `0x40400000`

## Pass criteria

| Check | Target | Status |
|-------|--------|--------|
| Synthesis / timing | WNS ≥ 0 @ 100 MHz, fits xc7z020 | **PASS** — see `synthesis_timing.txt`, `synthesis_utilisation.txt` |
| Stream golden | 200/200 PASS via DMA | **PASS** — see `board_golden.txt` |
| Functional | Same classes/distances as Phase 1 | **PASS** — same `cosim_core` vectors |
| Throughput bench | vs Phase 1 ~3 µs/window baseline | **Pending** — run `HDC_DMA/run_bench.sh` |

## Run (HDC_DMA folder)

```bash
# Golden test over JTAG (done — 200/200 PASS)
bash "/home/bsp-lab/Desktop/Final HDC/HDC_DMA/run_jtag.sh"

# Build + run DMA throughput bench (optional)
bash "/home/bsp-lab/Desktop/Final HDC/HDC_DMA/build.sh"
bash "/home/bsp-lab/Desktop/Final HDC/HDC_DMA/run_bench.sh"
```

## Software

| File | Role |
|------|------|
| `sw/hdc_dma_stream_golden_test.c` | 200-case DMA golden test |
| `sw/hdc_dma_stream_bench.c` | Latency bench + golden spot-check (Phase 2) |
| `sw/hdc_dma_stream.c` | DMA stream driver |
| `sw/hdc_core_regs.c` | Config load (proto/mask) |

## Results files

| File | Description |
|------|-------------|
| `board_golden.txt` | DMA golden test — **PASS 200/200** |
| `board_bench.txt` | Stream throughput / latency vs Phase 1 baseline |
| `synthesis_timing.txt` | WNS +0.023 ns @ 100 MHz |
| `synthesis_utilisation.txt` | 66% LUT, 96% slices |

## Phase 1 comparison

| Metric | Phase 1 (AXI-Lite) | Phase 2 (DMA stream) |
|--------|--------------------|----------------------|
| Golden | 200/200 PASS | 200/200 PASS |
| Latency | ~3 µs/window | *pending bench* |
| Path | START/DONE poll | MM2S + S2MM |

See `results/phase1/board_bench.txt` for Phase 1 baseline.
