# Phase 1 — AXI-Lite inference on ZedBoard

**Target:** ZedBoard (xc7z020clg484-1), Vivado 2024.2, FCLK_CLK0 = 100 MHz  
**PL module:** `hdc_core_axi_lite_bd_wrapper` @ `0x43C00000`  
**Software:** `sw/hdc_core_golden_test.c`, `sw/hdc_core_bench.c`, `sw/hdc_core_regs.c`

## Pass criteria (all met)

- [x] Bitstream programs and smoke test returns expected class/dist
- [x] Golden batch **200/200 PASS** (same vectors as `sim/run_core_axi_cosim.do`)
- [x] Latency bench: min/mean/max reported
- [x] Timing closure WNS ≥ 0 @ 100 MHz

## Files in this directory

| File | Description |
|------|-------------|
| `board_smoke.txt` | First on-board inference (single window) |
| `board_golden.txt` | 200-case golden test log |
| `board_bench.txt` | Latency / throughput micro-benchmark |
| `synthesis_utilisation.txt` | Post-route utilisation |
| `synthesis_timing.txt` | Timing summary |
