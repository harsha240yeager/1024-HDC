# Figure caption draft — `twist1_three_baselines_keep0125.pdf` (issue #23)

**Suggested LaTeX caption:**

> **Iso-density baselines at fixed keep ratio (128/1024 bits).**
> Spatial mean accuracy (5 subjects, Protocol HDC-2) for Fisher-informed pruning
> vs random-all (uniform over all bit positions) vs random-support (uniform over
> active bit positions only). Error bars: ±1 std over random seeds (30 for
> random-all on Twist 1; 5 for random-support from ranking baselines).
> **(a)** hdc_ref RTL encoder (~209 active bits): informed 72.65%, random-all
> 65.75±3.20%, random-support 71.45% — gap informed−random-all **+6.90 pp**.
> **(b)** Stage B BSC encoder (~335 active bits): informed 89.01%, random-all
> 86.19±3.63%, random-support 88.72% — gap **+2.82 pp** (attenuated but non-zero).

**Takeaway:** Random-support closes part of the informed−random-all gap on sparse
RTL support but does not eliminate it; on dense Stage B the absolute gap shrinks
while random-support tracks informed more closely.

**Sources:**
- `results/protocol_v2/twist1_keep0125_30seed/twist1_results.json`
- `results/protocol_v2/ranking_baselines/ranking_baselines_results.json`
- `results/protocol_v2/twist1_stage_b_keep0125/twist1_results.json`
- `results/protocol_v2/twist1_stage_b/ranking_baselines_results.json`

**Regenerate:**
```bash
python3 python_ref/plot_results.py --paper --only twist1_three
```
