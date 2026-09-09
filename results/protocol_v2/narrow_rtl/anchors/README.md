# Narrow board bring-up (issue #31)

**Status:** software ready; **hardware not connected** on lab machine (2026-09-07).

## Prepared artifacts

| Item | Path |
|------|------|
| Narrow bitstream | `board/HDC_DMA/app/_ide/bitstream/design_1_wrapper.bit` (md5 `d28d5243…`, synced from integrated impl) |
| Narrow EMG ELF | `board/HDC_DMA/app/build/Final_HDC_dma_emg.elf` (built with `-DHDC_NARROW`) |
| Pre-gathered protos | `sw/emg_board_vectors.h` → `emg_proto_narrow64[]`, K=128 |
| Export ref (anchor C) | 64.58% (`EMG_EXPORT_REF_ACCURACY_X1000=64582`) |

## Run when ZedBoard is connected

1. Power on ZedBoard; JP7 = JTAG; connect PROG/UART USB (Digilent `0403:6014` → `/dev/ttyUSB0`).
2. From repo root:

```bash
export HDC_VIVADO_ROOT="$HOME/Desktop/Final HDC/FInal_HDC"
export HDC_ANCHOR_SKIP_PATCH=1   # headers already patched for anchor C + narrow
bash board/HDC_DMA/run_anchor_replay.sh C --narrow
```

Results land in `results/protocol_v2/narrow_rtl/anchors/anchor_C/board_emg_replay.txt`.

## Expected outcome

Board accuracy within **0.5 pp** of export ref (~64.58%) — same gate as baseline anchor C replay.
