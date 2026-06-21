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
| `phase3/` | Batch throughput, EMG replay, energy (planned) |
| `sim/` | Optional exported co-sim summaries (not waveforms) |

## Status (last updated: 2026-06-21)

| Milestone | Status |
|-----------|--------|
| RTL co-sim (7 harnesses) | PASS |
| Phase 1 — AXI-Lite @ 0x43C00000 | **COMPLETE** |
| Phase 2 — AXI-DMA + stream system | **COMPLETE** |
| Phase 3 — measurements (throughput, EMG, energy) | **Not started** |

See per-phase README files for detail.

## How to update

1. Run the test on the board (see `board/HDC_DMA/` for Phase 2).
2. Copy structured output into the matching `.txt` file under `phaseN/`.
3. After Vivado builds, paste utilisation / timing into `phaseN/synthesis_*.txt`.
4. Commit with a short message, e.g. `results: phase2 stream golden 200/200`.

```bash
bash board/HDC_DMA/run_jtag.sh
bash board/HDC_DMA/run_bench.sh
git add results/
git commit -m "results: update phase2 board bench"
git push
```
