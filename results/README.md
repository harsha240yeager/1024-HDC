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
| `phase3/` | Batch bench + EMG replay (**complete**); energy (**pending**) |
| `sim/` | Optional exported co-sim summaries (not waveforms) |

## Status (last updated: 2026-06-23)

| Milestone | Status |
|-----------|--------|
| RTL co-sim (7 harnesses) | PASS |
| Phase 1 — AXI-Lite @ 0x43C00000 | **COMPLETE** |
| Phase 2 — AXI-DMA + stream system | **COMPLETE** |
| Phase 3 — batch bench (latency + 200-window + golden) | **COMPLETE** |
| Phase 3 — EMG replay (RTL encoder, 658k windows) | **PASS** — 74.24% board == export ref |
| Phase 3 — energy measurement | **NOT STARTED** (template only) |

**Dual baseline:** Stage B reference **90.30%** (Python) vs RTL encoder **74.24%**
(board). See `docs/Baseline_vs_RTL_Encoder.md`.

See `phase3/README.md` for the close checklist and remaining paper items.

## How to update

```bash
cd board/HDC_DMA
bash build_sw.sh
bash run_phase3_bench.sh      # → results/phase3/board_bench.txt
bash run_phase3_emg.sh        # → results/phase3/board_emg_replay.txt
git add results/phase3/
git commit -m "results: phase3 ..."
git push
```
