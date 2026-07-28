## Priority: P1 · Paper 1

Re-verify narrow/gated RTL: co-simulation + 200-vector golden batch.

## Goal

Same verification bar as original bring-up — no accuracy regression from H1 RTL.

## Requirements

- [ ] Re-run affected ModelSim harnesses (`sim/`, golden vectors)
- [ ] Regenerate vectors if encoder/AM interface changed
- [ ] 200/200 golden batch PASS on board (`sw/hdc_dma_stream_bench.c`)
- [ ] Log: `results/protocol_v2/narrow_rtl/cosim.log`, `board_golden.txt`

## Done when

- [ ] All harnesses PASS; golden 200/200
- [ ] Blocks #31 board anchor eval

## Blocked by

- #29 implement + bitstream
