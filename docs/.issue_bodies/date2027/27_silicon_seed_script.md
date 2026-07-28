## Priority: P1 · Paper 1 · Enables #26

Automation: loop silicon random-mask seeds 1–9 on ZedBoard.

## Goal

One script to reduce hand-coordinated JTAG + replay errors when running #26.

## Requirements

- [ ] Add `scripts/run_silicon_random_seeds.sh` (bash; Git bash on Windows OK)
- [ ] Args: `--seeds 1-9`, `--keep 0.125`, `--out results/protocol_v2/twist1_silicon`
- [ ] Steps per seed: export/program mask → run board replay → capture log
- [ ] Idempotent: skip seed if `board_emg_replay.txt` exists and `--resume`
- [ ] Document in `results/protocol_v2/twist1_silicon/README.md`

## Done when

- [ ] Script committed; dry-run documented
- [ ] Used to produce #26 artifacts

## References

- `scripts/run_golden_jtag.sh`, `scripts/run_golden_jtag.tcl`
- `scripts/prep_emg_board_test.sh`
