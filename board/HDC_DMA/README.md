# HDC_DMA — Phase 2/3 Stream + AXI DMA (ZedBoard)

Self-contained Vitis workspace inside the **1024-HDC** repo for Phase 2 DMA bring-up
and Phase 3 batch measurement (scatter-gather DMA enabled).

## Quick start

```bash
cd board/HDC_DMA

export HDC_VIVADO_ROOT="/path/to/FInal_HDC"

bash build_sw.sh              # SW-only: golden + bench + batch ELFs

# Phase 2
bash run_jtag.sh              # host-side 200-case golden
bash run_golden_app.sh        # bare-metal golden app
bash run_bench.sh             # Phase 2 latency bench

# Phase 3 (batch measurement — COMPLETE in results/phase3/board_bench.txt)
bash run_phase3_bench.sh      # primary: JTAG → board_bench.txt
bash run_phase3_golden.sh     # optional golden regression
bash run_batch_bench.sh       # supplementary 10k sequential bench
```

**Latest board results (June 2026):** batch **~216k windows/s**, golden **200/200**,
SG DMA (`XPAR_AXI_DMA_0_INCLUDE_SG 1`). See `results/phase3/README.md`.

Full rebuild (Vivado project required):

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
bash ../../scripts/rebuild_sg_bitstream.sh   # SG + export + BSP + ELFs
# or
bash build.sh                                # XSA export + BSP + ELFs from repo
```

## JTAG + USB UART (simultaneous monitoring)

On ZedBoard the Digilent cable shares JTAG and UART on one USB link. For live
serial **during** EMG replay (plus JTAG at the same time), use the two-terminal
flow in [`docs/USB_UART_JTAG.md`](../../docs/USB_UART_JTAG.md).

Quick rules:

1. Open **picocom @ 115200** on `/dev/ttyUSB0` **before** starting JTAG.
2. Close Vivado Hardware Manager / Vitis debug (not picocom in another terminal).
3. Expect UART to freeze during the ~11 MB vector load; progress resumes once
   inference starts (firmware prints every 2000 windows after rebuild).

## JTAG tips

On ZedBoard the Digilent cable shares JTAG and UART. If a run fails:

1. Close minicom and Vitis debug sessions.
2. Re-run the script (PL program often succeeds on attempt 2–6).
3. Garbage DDR magic (e.g. `0xEA000049`) means retry — not a bench logic failure.

## Layout

```
board/HDC_DMA/
├── run_phase3_bench.sh      ← Phase 3 primary (JTAG readback)
├── run_phase3_golden.sh     ← optional golden regression
├── run_jtag.sh / run_golden_app.sh / run_bench.sh
├── run_batch_bench.sh       ← supplementary 10k bench
├── build_sw.sh              ← fast SW rebuild
├── build.sh                 ← full Vivado XSA + BSP regen + SW
├── scripts/
│   ├── regenerate_bsp_from_xsa.tcl   ← HSI BSP regen (picks up SG)
│   └── update_platform_from_xsa.tcl
└── app/build/Final_HDC_dma_{golden,bench,batch_bench}.elf
```

## DDR result layout (JTAG readback)

| Address | Magic | App |
|---------|-------|-----|
| `0x00100000` | `0xBEC00002` | Phase 2/3 bench (single-window + golden) |
| `0x00100100` | `0xBEC00003` | Batch metrics + golden app |
| `0x00100200` | `0xBEC00004` | Supplementary 10k batch bench |

## Results

| Phase | Path |
|-------|------|
| Phase 2 | `results/phase2/` |
| Phase 3 batch | `results/phase3/board_bench.txt` (**COMPLETE**, ~216k windows/s) |
| Phase 3 EMG / energy | EMG **PASS** (74.24%) — see `results/phase3/board_emg_replay.txt` |
