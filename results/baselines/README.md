# Tier 4 comparison baselines (P-may2026)

Frozen EMG protocol; same train/test split as Hook A and board replay.

| Baseline | Spatial mean accuracy | Notes |
|----------|----------------------|-------|
| **ARM HDC (C, hdc_ref)** | **74.15%** | 5 subjects, full test split; 32/32 encode verify vs Python |
| Board RTL encoder | **74.24%** | ZedBoard EMG replay (reference) |
| MLP int8 (quick, 2 subj) | 99.24% float / 60.85% int8 | ~5.8k params; quick run only — re-run full for paper |
| AXI-Lite PL path | — | Phase 1 done (latency baseline, not accuracy) |

## ARM HDC

- **Source:** `sw/hdc_arm_ref.c` (portable C, Cortex-A9 target)
- **Runner:** `python_ref/run_arm_hdc_baseline.py`
- **Results:** `arm_hdc_results.json` (full grid, 2026-06-29, 132 s on VDI)
- **Pending:** cross-compile + on-board timing/energy bench (vs PL ~10× claim)

## MLP

- **Runner:** `python_ref/run_mlp_baseline.py`
- **Results:** `mlp_results.json` (quick sanity so far)

## Regenerate

```bash
python3 python_ref/run_arm_hdc_baseline.py          # full (~2 min)
python3 python_ref/run_mlp_baseline.py              # full (~minutes)
python3 python_ref/run_baselines.py                 # both
```

Build host library: `bash scripts/build_hdc_arm_host.sh shared`
