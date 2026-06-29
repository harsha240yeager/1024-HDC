# Hook A — Python accuracy sweep (Pareto axes)

Generated: 2026-06-29T10:09:32Z
Engine: **hdc_ref** (RTL-matched `hdc_ref` / `encoder_top.sv`)
Mask: **informed_fisher** (Fisher-informed, train pooled per subject)

Energy on silicon (INA219) is **deferred**; `energy_proxy_d_keep = (D/1024)×keep_ratio`.
Area proxy from OOC synth: `results/dsweep/`.

## Spatial mean accuracy (5 subjects, TEST split)

| D | CNT_W | Keep | Prune % | Accuracy | Δ vs D=1024,CNT_W=6,keep=1 | Energy proxy | LUT (OOC) |
|---|-------|------|---------|----------|---------------------------|--------------|-------------|
| 1024 | 6 | 0.5 | 50.0 | **79.02%** | +0.00 pp | 0.5 | 28600 |
| 1024 | 6 | 1.0 | 0.0 | **79.02%** | +0.00 pp | 1.0 | 28600 |

## Regenerate

```bash
cd python_ref
python3 run_hook_a_sweep.py --quick    # sanity (~3 min, capped windows)
python3 run_hook_a_sweep.py            # full grid (hours)
```

Full JSON: `sweep_results.json`, CSV: `sweep_summary.csv`.
