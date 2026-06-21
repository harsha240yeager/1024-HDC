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
| `phase3/` | Batch throughput, EMG replay, energy — SW ready; board run pending |
| `sim/` | Optional exported co-sim summaries (not waveforms) |

## Status (last updated: 2026-06-21)

| Milestone | Status |
|-----------|--------|
| RTL co-sim (7 harnesses) | PASS |
| Phase 1 — AXI-Lite @ 0x43C00000 | **COMPLETE** |
| Phase 2 — AXI-DMA + stream system | **COMPLETE** |
| Phase 3 — batch bench + energy setup | SW ready; board run pending |

See per-phase README files for detail.

## How to update

1. Run the test on the board (see `board/HDC_DMA/` for Phase 2–3 stream apps).
2. Copy structured output into the matching `.txt` file under `phaseN/`.
3. After Vivado builds, paste utilisation / timing into `phaseN/synthesis_*.txt`.
4. Commit with a short message, e.g. `results: phase3 batch bench`.

```bash
bash board/HDC_DMA/run_bench.sh          # Phase 2 single-window (existing)
bash scripts/run_stream_bench_hdc.sh     # Phase 3 batch bench → results/phase3/
git add results/
git commit -m "results: update phase3 board bench"
git push
```
