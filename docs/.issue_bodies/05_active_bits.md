## Priority: P1 (blocked by #1)

Investigate why only **~257 of 1024** bit positions vary on TRAIN data.

## Tasks

- [ ] `active_bit_support()` in `hdc_ref.py`
- [ ] Report active count: subjects × seeds × encoders × D
- [ ] Diagnose: item memory, 20-bind bundling, majority collapse
- [ ] Explain lossless keep=512 (512 > active support)
- [ ] **Fair random baseline:** sample from active support only

Plan: [Phase 5a](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-5--active-bit-ablation-257-positions--ranking-baselines)

Related: #9 (ranking baselines)
