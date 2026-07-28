## Priority: P2 · Paper 2 · Optional

Real per-feature encoder (non-redundant `level21_to_grid`).

## Goal

Raise ~73% RTL accuracy ceiling; increase active support for stronger generalization claims.

## Requirements

- [ ] Define feature source (Hudgins, multi-sample window, etc.)
- [ ] Update export + `HDCEngine` grid fill — **breaks bit-exact** with current silicon
- [ ] Python-only iso-density rerun OR full re-export + board re-verify (major scope)
- [ ] Document tradeoff in issue before implementation

## Done when

- [ ] Decision: Python-only Paper 2 extension **or** full platform re-baseline
- [ ] If pursued: new results dir `results/protocol_v2/encoder_v2/`

## Note

Large scope — **not** required for DATE if #21 Stage-B covers dense-support question.
