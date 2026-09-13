# Narrow board bring-up (issue #31)

**Status:** anchor C board replay **PASS** (2026-09-13).

## Prepared artifacts

| Item | Path |
|------|------|
| Narrow bitstream | `board/HDC_DMA/app/_ide/bitstream/design_1_wrapper.bit` (md5 `d28d5243…`, synced from integrated impl) |
| Narrow EMG ELF | `board/HDC_DMA/app/build/Final_HDC_dma_emg.elf` (built with `-DHDC_NARROW`) |
| Pre-gathered protos | `sw/emg_board_vectors.h` → `emg_proto_narrow64[]`, K=128 |
| Export ref (anchor C) | 72.85% (`EMG_EXPORT_REF_ACCURACY_X1000=72850`) — Fisher pooled, same as baseline |

## Board result (anchor C)

| Metric | Value |
|--------|-------|
| Board accuracy | 72.84% (359522 / 493512) |
| Export ref | 72.85% |
| Delta | 0.01 pp — **PASS** |

Narrow gather is bit-exact to masked Fisher classify; board accuracy matches baseline anchor C.

## Latency (narrow bench, 2026-09-13)

| Metric | Baseline | Narrow (K=128) |
|--------|----------|----------------|
| Batch 200 total | 926 µs | **556 µs** |
| Mean/window | 4.63 µs | **2.78 µs** (~1.67×) |
| Golden | 200/200 PASS | 200/200 PASS |

Artifact: `results/protocol_v2/narrow_rtl/board_bench.txt`

## Run when ZedBoard is connected

1. Power on ZedBoard; JP7 = JTAG; connect PROG/UART USB (Digilent `0403:6014` → `/dev/ttyUSB0`).
2. From repo root:

```bash
export HDC_VIVADO_ROOT="$HOME/Desktop/Final HDC/FInal_HDC"
bash board/HDC_DMA/run_anchor_replay.sh C --narrow
```

Results land in `results/protocol_v2/narrow_rtl/anchors/anchor_C/board_emg_replay.txt`.

## Expected outcome

Board accuracy within **0.5 pp** of Fisher export ref (~72.85%) — same gate as baseline anchor C replay.
