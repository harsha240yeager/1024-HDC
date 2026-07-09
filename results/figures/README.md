# Paper figures (static PNG + PDF)

Generated from committed `results/` data only — nothing recomputed.

```bash
python3 python_ref/plot_results.py
python3 python_ref/plot_results.py --out results/figures
```

| File | Content |
|------|---------|
| **`hookA_pareto_measured.png`** | **Main Hook A Pareto** — (a) Python OOC LUT sweep + placed silicon ★; (b) measured µJ/w at A/B/C/ARM (no proxy overlay) |
| `hookA_pareto_area.png` | Python accuracy vs OOC LUT (CNT_W=6, unpruned) |
| `hookA_pruning.png` | Python acc + **dynamic energy proxy** vs prune % (D=1024); footnote: measured PL ≈ flat |
| `hookA_accuracy_vs_D.png` | Accuracy vs D — CNT_W=3 vs CNT_W=4–6 (collapsed legend) |
| `per_subject_accuracy.png` | ARM HDC ref (host sim) vs MLP per subject |
| `spatial_vs_spatiotemporal.png` | MAP vs BSC spatial/temporal |
| **`fisher_heatmap.png`** | **Fisher masks** — (a) pooled score heatmap 16×64; (b) rank + anchor cutoffs; (c–d) informed masks @ keep=0.5 / 0.125 |
| **`baselines_bar.png`** | **Deployment baselines** — PL board vs ARM host sim vs MLP; latency/energy measured ZedBoard |
| **`twist1_informed_vs_random.png`** | Twist 1 @ keep=0.5 — supplementary (+1.7 pp gap) |
| **`twist1_informed_vs_random_keep0125.png`** | **Twist 1 headline** @ keep=0.125 — informed vs random (+8.6 pp) |

Sources: [`hook_a/sweep_summary.csv`](../hook_a/sweep_summary.csv),
[`hook_a/fisher_pooled.npz`](../hook_a/fisher_pooled.npz) (from `scripts/export_fisher_pooled.py`),
[`phase3/energy_summary.txt`](../phase3/energy_summary.txt),
[`phase3/anchors/`](../phase3/anchors/),
[`baselines/`](../baselines/),
[`twist1/`](../twist1/),
[`twist1_keep0125/`](../twist1_keep0125/).
