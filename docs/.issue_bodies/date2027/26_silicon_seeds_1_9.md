## Priority: P0 · Paper 1 + Paper 2 · **Required for strong Paper 1**

Silicon iso-density: random-mask **seeds 1–9** on ZedBoard (seed 0 done).

## Goal

Turn the single +10.33 pp silicon point into a **distribution** (mean ± std over
≥5 seeds). Closes legacy #3 FPGA bullet.

## Requirements

- [ ] For each seed 1..9: program **pooled random mask** at keep=0.125 via JTAG/AXI
- [ ] Replay full S1–S5 TEST cohort (493,512 windows); log `board_emg_replay.txt`
- [ ] Compare vs **informed anchor C** (72.84% pooled) — same cohort
- [ ] Report per-seed gap (pp); aggregate mean ± std
- [ ] Output: `results/protocol_v2/twist1_silicon/random_seed_{1..9}/`

## Done when

- [ ] ≥5 seeds complete with PASS (|board − ref| ≤ 0.5 pp for informed; random vs informed gap logged)
- [ ] Summary CSV/JSON: `results/protocol_v2/twist1_silicon/seed_summary.json`
- [ ] Paper: replace “one seed” with mean ± std or report range

## Lab notes

- Seed 0: `results/protocol_v2/twist1_silicon/random_seed_0/` (exists)
- Mask reprogram without full bitstream reload — see board docs / `run_golden_jtag.tcl`

## Supersedes

- Open items in **#3** (FPGA random seeds)

## Blocked by

- #27 automation script (recommended, not strict)
