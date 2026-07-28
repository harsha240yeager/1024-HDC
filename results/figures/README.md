# Paper figures (static PNG + PDF)

Generated from committed `results/` data only — nothing recomputed.

```bash
python3 python_ref/plot_results.py              # 300 dpi (default)
python3 python_ref/plot_results.py --paper      # IEEE single-column: no suptitles, compact size
python3 python_ref/plot_results.py --paper --only twist1_three   # issue #23 hero only
python3 python_ref/plot_results.py --dpi 600    # extra-high PNG rasterization
python3 python_ref/plot_results.py --out results/figures
```

**Export settings:** serif fonts, editable PDF text (`pdf.fonttype=42`), 300 dpi PNG/PDF,
`tight` bounding box. Use the `.pdf` for LaTeX `\includegraphics`; PNG for slides.

| File | Content |
|------|---------|
| **`hookA_pareto_measured.png`** | **Main Hook A Pareto** — (a) Python OOC LUT sweep + placed silicon ★; (b) measured µJ/w at A/B/C/ARM |
| `hookA_pareto_area.png` | Python accuracy vs OOC LUT (CNT_W=6, unpruned) |
| `hookA_pruning.png` | Python acc + dynamic energy proxy vs prune % (D=1024) |
| `hookA_accuracy_vs_D.png` | Accuracy vs D — CNT_W=3 vs CNT_W=4–6 |
| `per_subject_accuracy.png` | ARM HDC ref (host sim) vs MLP per subject |
| `spatial_vs_spatiotemporal.png` | MAP vs BSC spatial/temporal |
| **`fisher_heatmap.png`** | Fisher masks — score heatmap, rank curve, informed @ keep=0.5 / 0.125 |
| **`baselines_bar.png`** | PL board vs ARM host sim vs MLP; latency/energy measured ZedBoard |
| **`twist1_informed_vs_random.png`** | Twist 1 @ keep=0.5 — supplementary (+1.7 pp) |
| **`twist1_informed_vs_random_keep0125.png`** | **Twist 1 headline** @ keep=0.125 (+8.6 pp) |
| **`twist1_three_baselines_keep0125.png`** | **Issue #23 hero** — informed / random-all / random-support @ keep=0.125 (hdc_ref + Stage B) |
| **`twist2_cross_subject.png`** | Twist 2 pilot — S1–3 → S4–5 (+0.86 pp) |
| **`twist2_cross_subject_36.png`** | **Twist 2 @ 36 UCI subjects** — S1–18 → S19–36 (0.00 pp gap) |

Sources: [`hook_a/sweep_summary.csv`](../hook_a/sweep_summary.csv),
[`hook_a/fisher_pooled.npz`](../hook_a/fisher_pooled.npz),
[`phase3/energy_summary.txt`](../phase3/energy_summary.txt),
[`twist1/`](../twist1/), [`twist1_keep0125/`](../twist1_keep0125/),
[`twist2/`](../twist2/), [`twist2_36/`](../twist2_36/).
