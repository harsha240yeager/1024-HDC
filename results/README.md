# Board and synthesis results

This folder stores **measured outcomes** from Zynq bring-up, benchmarks, and
(later) energy / Pareto studies. Update the files here after each board run or
bitstream build — do not edit golden vectors or RTL to “fix” a mismatch; fix the
hardware or driver instead.

## Layout

| Path | Contents |
|------|----------|
| `phase1/` | AXI-Lite path on ZedBoard (**complete**) |
| `phase2/` | AXI-DMA + stream path (**complete**) |
| `phase3/` | Batch bench (**complete**); EMG v1 RTL parity (**complete**); EMG v2 + energy (**pending**) |
| `sim/` | Optional exported co-sim summaries (not waveforms) |

## Status (last updated: 2026-06-12)

| Milestone | Status |
|-----------|--------|
| RTL co-sim (7 harnesses) | PASS |
| Phase 1 — AXI-Lite @ 0x43C00000 | **COMPLETE** |
| Phase 2 — AXI-DMA + stream system | **COMPLETE** |
| Phase 3 — batch bench (latency + 200-window + golden) | **COMPLETE** |
| Phase 3 — EMG v1 RTL parity (500 windows, subject 1) | **COMPLETE** — board 59.60% == export 59.60% |
| Phase 3 — EMG v2 full TEST-split replay | **PENDING** |
| Phase 3 — energy measurement | **NOT STARTED** (template only) |

See `phase3/README.md` for the close checklist and remaining paper items.

## How to update

```bash
cd board/HDC_DMA
bash build_sw.sh
bash run_phase3_bench.sh      # → results/phase3/board_bench.txt
git add results/phase3/
git commit -m "results: phase3 batch bench"
git push
```
