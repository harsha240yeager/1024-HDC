# HDC_DMA — Phase 2/3 Stream + AXI DMA (ZedBoard)

Self-contained Vitis workspace inside the **1024-HDC** repo for Phase 2 DMA bring-up
and Phase 3 measurement runs.

## Quick start

```bash
cd board/HDC_DMA

# Point to your Vivado project (contains export_hw_platform.tcl + impl bitstream)
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"

# Full build (XSA export + BSP + FSBL + all ELFs)
bash build.sh

# SW-only rebuild (faster — no Vivado)
bash build_sw.sh

# Phase 2 verification
bash run_jtag.sh           # host-side 200-case golden (JTAG)
bash run_golden_app.sh     # bare-metal sw/hdc_dma_stream_golden_test.c
bash run_bench.sh          # latency bench vs Phase 1 ~3 µs baseline

# Phase 3 measurements
bash run_batch_bench.sh    # 10k sustained batch + E2E latency proxy
```

Expected golden result: `PASS: 200/200 stream golden cases`

## Layout

```
board/HDC_DMA/
├── run_jtag.sh              ← host-side JTAG golden test
├── run_golden_app.sh        ← bare-metal golden app (DDR @ 0x00100100)
├── run_bench.sh             ← Phase 2 latency bench
├── run_batch_bench.sh       ← Phase 3 sustained throughput + E2E proxy
├── build.sh                 ← full rebuild (Vivado XSA + SW)
├── build_sw.sh              ← SW-only (golden + bench + batch ELFs)
├── _ide/
│   ├── common.sh
│   ├── paths.tcl
│   ├── program_pl.tcl
│   ├── run_golden_load.tcl
│   ├── run_bench_load.tcl / run_bench_all.tcl
│   └── run_batch_bench_load.tcl
├── platform/                # Vitis platform (Final_HDC): BSP, FSBL, XPFM
└── app/build/               # Final_HDC_dma_{golden,bench,batch_bench}.elf
```

Host-side golden Tcl: `scripts/run_stream_golden_jtag.tcl`  
(set `HDC_IDE=board/HDC_DMA/_ide` automatically by `run_jtag.sh`)

## DDR result layout (JTAG readback)

| Address | Magic | App |
|---------|-------|-----|
| `0x00100000` | `0xBEC00002` | Phase 2 latency bench |
| `0x00100100` | `0xBEC00003` | Phase 2 golden app |
| `0x00100200` | `0xBEC00004` | Phase 3 batch bench |
| `0x00100300` | `0xBEC00005` | Phase 3 EMG replay (scaffold) |

## Related paths in this repo

| Item | Path |
|------|------|
| SW sources | `sw/` |
| Golden vectors | `python_ref/vectors/cosim_core/` |
| Phase 2 results | `results/phase2/` |
| Phase 3 results | `results/phase3/` |
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

| Run | Default log dir | Archived to |
|-----|-----------------|-------------|
| `run_jtag.sh` | `/tmp/hdc_dma_jtag/` | `results/phase2/logs/` |
| `run_golden_app.sh` | `/tmp/hdc_dma_golden_app/` | `results/phase2/logs/` |
| `run_bench.sh` | `/tmp/hdc_dma_bench/` | `results/phase2/logs/` |
| `run_batch_bench.sh` | `/tmp/hdc_dma_batch_bench/` | `results/phase3/logs/` |
