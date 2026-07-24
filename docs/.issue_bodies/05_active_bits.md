## Priority: P1

Investigate why only **~203–210 of 1024** bit positions vary under HDC-2
(legacy issue text said ~257 from an earlier protocol snapshot).

## Tasks

- [x] `active_bit_support()` / `mask_random_from_support()` in `hdc_ref.py`
- [x] Report active count: subjects × seeds × D (`run_active_bit_ablation.py`)
- [x] Diagnose: continuous value ROM flip budget, 20-bind bundling, majority collapse
- [x] Explain lossless keep=512 (512 > active support)
- [x] **Fair random baseline:** sample from active support only

Outputs: `results/protocol_v2/active_bits/`

Plan: [Phase 5a](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-5--active-bit-ablation-257-positions--ranking-baselines)

Related: #9 (ranking baselines)
