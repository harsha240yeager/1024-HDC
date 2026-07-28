## Priority: P1 · Paper 2 · Reviewer-trap disclosure

Document redundant feature axis in export path (`level21_to_grid`).

## Goal

Explain why 20 binds ≈ 4 binds in encoder ablation: each channel’s envelope level
is replicated across five feature slots. Preempt “what are your features?” questions.

## Requirements

- [ ] Document in `results/protocol_v2/encoder_ablation/README.md` (extend existing)
- [ ] Cite `scripts/export_emg_board_vectors.py::level21_to_grid`
- [ ] Confirm identical function used in all Python sweeps + board export
- [ ] Paper: half-sentence in encoder subsection OR limitations (integration #36)
- [ ] Optional follow-up: track as #34 if fixing encoder (real features)

## Done when

- [ ] README committed; no inconsistency between Python and board pipelines
- [ ] Advisor/professor FAQ answered in repo docs

## Data already exists

- `python_ref/run_encoder_ablation.py` — 20 vs 4 binds ≈ same accuracy
