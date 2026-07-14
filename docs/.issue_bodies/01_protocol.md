## Priority: P0 BLOCKER

Fix train/test protocol before any other experiments. Current `split_train_test()` in `scripts/export_emg_board_vectors.py` returns the **full recording** as test while training uses the first 25% of each class → leakage.

## Protocol HDC-2

- Train: first 25% of each class (unchanged selection rule)
- Test: remaining 75% — **strictly disjoint indices**
- Optional: drop ±1 window at partition boundary
- Prototypes + Fisher scores: TRAIN only
- Report per-subject train/test window counts; overlap must be 0

## Tasks

- [ ] Add `python_ref/config/emg_baseline_v2.json`
- [ ] Rewrite `split_train_test()` + propagate to all sweep scripts
- [ ] Add `scripts/audit_split_leakage.py`
- [ ] Rerun: full-width acc, Twist 1, Hook A, ARM/FPGA, cross-subject, silicon replay

## Plan

See [`docs/DATE_REVISION_PLAN.md`](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-1--fix-traintest-protocol-blocker)

**Gate:** overlap = 0 for all subjects before closing this issue.
