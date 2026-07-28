## Priority: P1 · Paper 1 · **Required for strong Paper 1**

Board evaluation: anchors A/B/C + LUT/energy/latency vs keep on **new RTL**.

## Goal

Main Paper 1 result: Pareto-style evidence that keep ratio affects **physical** metrics.

## Requirements

- [ ] Replay anchors A, B, C on narrow/gated bitstream (accuracy vs export ref)
- [ ] INA219 energy runs (n=3) per anchor — idle-calibrated l.b.
- [ ] Latency: Phase 3 batch 200-window mean
- [ ] Compare to baseline RTL numbers (Table anchors + 12 µJ flat)
- [ ] Sweep optional: keep programmed via mask at fixed bitstream (if supported)

## Done when

- [ ] `results/protocol_v2/narrow_rtl/anchors/` committed
- [ ] **Gate met:** ≥10% LUT **or** ≥5% energy/latency improvement at keep=0.125 vs baseline at same accuracy band
- [ ] Summary table ready for paper Fig + Table

## Blocked by

- #30 verification PASS

## References

- `results/phase3/energy_summary.txt` (baseline)
- `results/protocol_v2/anchors/` (baseline accuracies)
