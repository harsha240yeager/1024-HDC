## Priority: P0 · Paper 1 · **Required for strong Paper 1**

Implement narrow/gated `popcount_am` (or parallel narrow AM) + resynthesize.

## Goal

RTL implementation of design approved in #28; out-of-context and integrated synth.

## Requirements

- [ ] RTL changes in `rtl/` (+ wrappers if needed)
- [ ] Update golden Python only if semantics change (should not)
- [ ] OOC synth @ D=1024: util report vs baseline
- [ ] Integrated bitstream via `board/HDC_DMA/` flow
- [ ] Post-route timing still closes 100 MHz (or report Fmax)

## Done when

- [ ] Utilization CSV committed: `results/dsweep/narrow_vs_baseline_util.csv`
- [ ] Bitstream programs on ZedBoard
- [ ] Blocks #30 verification

## Blocked by

- #28 design sign-off
