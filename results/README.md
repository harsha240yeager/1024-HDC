# Board and synthesis results

This folder stores **measured outcomes** from Zynq bring-up, benchmarks, and
(later) energy / Pareto studies. Update the files here after each board run or
bitstream build — do not edit golden vectors or RTL to “fix” a mismatch; fix the
hardware or driver instead.

## Layout

| Path | Contents |
|------|----------|
| `phase1/` | AXI-Lite path on ZedBoard (complete) |
| `phase2/` | AXI-DMA + stream path (pending bitstream) |
| `sim/` | Optional exported co-sim summaries (not waveforms) |

## How to update

1. Run the test on the board (Vitis bare-metal app, UART 115200).
2. Copy UART log or structured output into the matching `.txt` file.
3. After Vivado builds, paste utilisation / timing reports into `phaseN/synthesis_*.txt`.
4. Commit with a short message, e.g. `results: phase2 stream golden 200/200`.

```bash
# Example after a board run on the VDI
cp ~/1024-HDC/results/phase1_board.txt results/phase1/board_bench.txt
git add results/
git commit -m "results: update phase1 board bench"
git push
```

## Status (last updated: 2026-06-12)

| Milestone | Status |
|-----------|--------|
| RTL co-sim (7 harnesses) | PASS |
| Phase 1 — AXI-Lite @ 0x43C00000 | **COMPLETE** |
| Phase 2 — AXI-DMA + stream system | RTL + SW ready; board pending |

See per-phase README files for detail.
