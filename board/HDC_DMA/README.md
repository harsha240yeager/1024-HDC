# HDC_DMA — Phase 2 Stream + AXI DMA (ZedBoard)

Self-contained Vitis workspace inside the **1024-HDC** repo for Phase 2 DMA bring-up.

## Quick start

```bash
cd board/HDC_DMA

# Point to your Vivado project (contains export_hw_platform.tcl + impl bitstream)
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"

# Build BSP, FSBL, golden + bench ELFs
bash build.sh

# Program board + run 200-case golden test over JTAG (recommended)
bash run_jtag.sh

# Optional: DMA latency bench vs Phase 1 ~3 µs baseline
bash run_bench.sh
```

Expected golden result: `PASS: 200/200 stream golden cases`

## Layout

```
board/HDC_DMA/
├── run_jtag.sh          ← main run (JTAG golden test)
├── run_program.sh       ← program bitstream + bare-metal app
├── run_bench.sh         ← DMA latency bench + JTAG readback
├── build.sh             ← rebuild BSP, FSBL, ELFs
├── _ide/
│   ├── common.sh                    # JTAG helpers
│   ├── paths.tcl                    # artifact paths
│   ├── program_pl.tcl               # PL + PS7 + FSBL only
│   ├── program_board.tcl            # full program with app
│   ├── run_bench_all.tcl            # program bench + poll DDR
│   ├── program_board_helpers.tcl
│   └── ps7_init_helpers.tcl
├── platform/            # Vitis platform (Final_HDC): BSP, FSBL, XPFM
└── app/                 # DMA golden + bench apps, bitstream, ps7_init
```

Host-side golden Tcl (same vectors): `scripts/run_stream_golden_jtag.tcl`  
(set `HDC_IDE=board/HDC_DMA/_ide` automatically by `run_jtag.sh`)

## Related paths in this repo

| Item | Path |
|------|------|
| SW sources | `sw/` |
| Golden vectors | `python_ref/vectors/cosim_core/` |
| Measured results | `results/phase2/` |
| RTL reference pack | `vivado_pack/` |

## Hardware map

| Block | Base address |
|-------|--------------|
| Stream config (proto/mask) | `0x43C00000` |
| AXI DMA | `0x40400000` |

## Environment

| Variable | Purpose |
|----------|---------|
| `HDC_VIVADO_ROOT` | Vivado `FInal_HDC` project dir (required for `build.sh`) |
| `HDC_GOLDEN_VECDIR` | Override golden vector directory |
| `HDC_LOG_DIR` | JTAG log output directory |

## Logs

| Run | Default log dir |
|-----|-----------------|
| `run_jtag.sh` | `/tmp/hdc_dma_jtag/` |
| `run_bench.sh` | `/tmp/hdc_dma_bench/` |
