## Priority: P0 · Paper 1 · **Required for strong Paper 1**

Design: physically **narrow** or **clock-gated** masked Hamming datapath.

## Goal

Answer DATE objection “mask does not reduce hardware.” Pick **one** approach:

**Option A — Narrow compare:** Only popcount/XOR enabled mask lanes (128-bit effective at keep=0.125).

**Option B — Clock-gate:** Full-width XOR but gate popcount lanes where mask=0.

## Requirements

- [ ] Written micro-arch spec in `docs/H1_narrow_datapath_design.md` (1–2 pages)
- [ ] Area/latency expectation vs baseline `popcount_am.sv`
- [ ] Verification plan: which co-sim harnesses must re-run
- [ ] Confirm anchor accuracy gate unchanged (±0.5 pp)

## Done when

- [ ] Design reviewed (advisor sign-off optional)
- [ ] RTL task breakdown for #29 issued

## Gate (from split plan)

≥10% LUT reduction **or** measurable µJ/latency improvement at keep=0.125 vs baseline RTL.

## References

- `rtl/popcount_am.sv`, `rtl/pruning_mask.sv`
- Paper Sec. VI — fixed-width XOR-then-mask null result
