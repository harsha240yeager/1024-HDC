## Priority: P1 · Paper 1 · **Required for strong Paper 1**

Board evaluation: anchors A/B/C + LUT/energy/latency vs keep on **new RTL**.

## Goal

Main Paper 1 result: Pareto-style evidence that keep ratio affects **physical** metrics.

## Requirements

- [x] Replay anchor C on narrow/gated bitstream (A/B documented n/a — K=128 only)
- [ ] INA219 energy runs (n=3) on narrow PL — `scripts/run_narrow_energy_campaign.sh` (Pi offline 2026-09-17)
- [x] Latency: Phase 3 batch 200-window mean (`board_bench.txt`)
- [x] Compare to baseline RTL numbers (LUT, latency, accuracy, baseline energy ref)
- [ ] Sweep optional: keep programmed via mask at fixed bitstream (if supported)

## Done when

- [x] `results/protocol_v2/narrow_rtl/anchors/` committed
- [x] **Gate met:** ≥10% LUT **or** ≥5% energy/latency improvement at keep=0.125 vs baseline at same accuracy band
- [x] Summary table ready for paper Fig + Table — `board_eval_summary.md`

## Blocked by

- #30 verification PASS

## References

- `results/phase3/energy_summary.txt` (baseline)
- `results/protocol_v2/anchors/` (baseline accuracies)
