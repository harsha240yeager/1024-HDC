## Summary

<!-- What changed and why (DATE revision phase if applicable) -->

## Phase / issue

- [ ] Links to GitHub issue #___ (DATE revision)
- [ ] HDC-2 gate: `python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline_v2.json` (if split-related)

## Test plan

- [ ] `python python_ref/tests/test_split_hdc2.py`
- [ ] `python scripts/audit_split_leakage.py --synthetic-only`
- [ ] `cd python_ref && python run_smoke_test.py`
- [ ] Other: <!-- board rerun, sweep, etc. -->

## Paper impact

- [ ] No headline accuracy numbers changed (or rerun complete under HDC-2)
- [ ] Results path: `results/protocol_v2/` (new) vs `results/` (HDC-1 legacy)
