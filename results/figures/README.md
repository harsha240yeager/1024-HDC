# Paper figures (static PNG + PDF)

Generated from committed `results/` data only — nothing recomputed.

```bash
python3 python_ref/plot_results.py
python3 python_ref/plot_results.py --out results/figures
```

| File | Content |
|------|---------|
| **`hookA_pareto_measured.png`** | **Main Hook A Pareto** — (a) accuracy vs LUT D-sweep + silicon D=1024; (b) measured µJ/w at anchors A/B/C/ARM |
| `hookA_pareto_area.png` | Python accuracy vs OOC LUT (CNT_W=6, unpruned) |
| `hookA_pruning.png` | Accuracy + energy proxy vs prune % (D=1024) |
| `hookA_accuracy_vs_D.png` | Accuracy vs D by CNT_W |
| `per_subject_accuracy.png` | HDC vs MLP per subject |
| `spatial_vs_spatiotemporal.png` | MAP vs BSC spatial/temporal |
| **`fisher_heatmap.png`** | **Fisher masks** — (a) pooled score heatmap 16×64; (b) rank + anchor cutoffs; (c–d) informed masks @ keep=0.5 / 0.125 |
| **`baselines_bar.png`** | **Deployment baselines** — PL DMA vs ARM HDC vs MLP int8: accuracy, latency (log), measured µJ/w (INA219) |

Sources: [`hook_a/sweep_summary.csv`](../hook_a/sweep_summary.csv),
[`hook_a/fisher_pooled.npz`](../hook_a/fisher_pooled.npz) (from `scripts/export_fisher_pooled.py`),
[`phase3/energy_summary.txt`](../phase3/energy_summary.txt),
[`phase3/anchors/`](../phase3/anchors/),
[`baselines/`](../baselines/).
