# Phase 2 — AXI-DMA + streaming inference

**Status:** RTL and bare-metal test app are in the repo; **board results pending**.

## Target architecture

- Replace `hdc_core_axi_lite_bd_wrapper` with `hdc_stream_system_bd_wrapper`
- AXI DMA (MM2S + S2MM, 32-bit, no SG) + HP0 to DDR
- Config @ `0x43C00000` (same STAGING / LOAD_PROTO / LOAD_MASK driver)
- DMA lite @ `0x40400000` (typical; confirm in Address Editor)

## Software

- `sw/hdc_dma_stream_golden_test.c`
- `sw/hdc_dma_stream.c`
- `sw/hdc_core_regs.c` (config load only)

## Pass criteria (not yet run on board)

- [ ] Bitstream builds, WNS ≥ 0 @ 100 MHz
- [ ] `PASS: 200/200 stream golden cases` over DMA
- [ ] Throughput bench vs Phase 1 baseline (~3 µs / window AXI-Lite)

## Files to add after board run

| File | Description |
|------|-------------|
| `board_golden.txt` | DMA golden test UART log |
| `board_bench.txt` | Stream throughput / latency |
| `synthesis_utilisation.txt` | Post-route util |
| `synthesis_timing.txt` | WNS / f_max |

See `vivado_pack/README.txt` Phase B for Vivado steps.
