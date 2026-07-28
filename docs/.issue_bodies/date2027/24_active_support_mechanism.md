## Priority: P1 · Paper 2 · Mechanism evidence

Quantify active support: value-table ceiling (327) vs data coverage (~209).

## Goal

Commit analysis showing **why** ~203–210 positions vary: structural ceiling from
continuous value item memory vs EMG data coverage — not bundling alone.

## Requirements

- [ ] Script or notebook: `active_bit_support` on `ItemMemory.value` → expect **327** (seed 42)
- [ ] On pooled TRAIN+TEST queries → **203–210** (match `seed_sensitivity_results.json`)
- [ ] Optional: uniform random envelope vs independent per-slot levels
- [ ] Output: `results/protocol_v2/active_support_mechanism/summary.json` + short README
- [ ] Table for paper: ceiling / random-input / real-data support counts

## Done when

- [ ] Numbers match discussion guide §5.2
- [ ] Paper text updated in integration issue (#36) — correct “~D/n_levels flips” wording if needed

## References

- `python_ref/hdc_ref.py` — `_continuous_value_table`, `active_bit_support`
- `docs/PAPER_DISCUSSION_GUIDE.md` §5.2
