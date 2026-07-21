# Twist 2 @ 36 UCI subjects — reproduction guide

Run cross-subject Fisher mask transfer on **36 UCI EMG subjects** (train S1–18 → test S19–36) on any machine with Python 3.10+.

**Protocol HDC-2** (disjoint 25%/75% split) uses `emg_baseline_v2.json`. Legacy HDC-1 configs remain as `twist2_36_sweep.json` (already have results under `results/twist2_36/`).

---

## What is on GitHub

| On GitHub | Not on GitHub (build locally) |
|-----------|-------------------------------|
| `python_ref/run_twist2_sweep.py` | `python_ref/HDC-EMG/dataset_36.mat` (~115 MB) |
| `python_ref/config/twist2_36_v2_sweep.json` | Raw UCI tree `data/EMG_data_for_gestures-master/` (~252 MB) |
| `python_ref/config/twist2_36_v2_keep05_sweep.json` | |
| `python_ref/config/emg_baseline_v2.json` | |
| `scripts/build_uci_emg_dataset.py` | |
| `scripts/run_twist2_36_v2_keep_grid.sh` | |
| `scripts/twist2_mask_audit_fast.py` | |
| Prior HDC-1 results: `results/twist2_36/` | |

`python_ref/HDC-EMG/` is **gitignored** (see `.gitignore`).

---

## 1. Clone and dependencies

```bash
git clone https://github.com/harsha240yeager/1024-HDC.git
cd 1024-HDC
pip install -r python_ref/requirements.txt
```

Requires: `numpy`, `scipy`, `matplotlib`.

---

## 2. Raw UCI data

**Option A — copy from an existing machine**

```bash
rsync -av other-pc:1024-HDC/data/EMG_data_for_gestures-master/ data/EMG_data_for_gestures-master/
```

**Option B — download**

1. Get [UCI EMG Data for Gestures](https://archive.ics.uci.edu/ml/datasets/emg+data+for+gestures) (or use `data/emg_uci.zip` if you have it).
2. Unzip so subject folders `01/`, `02/`, … `36/` live under:

```
data/EMG_data_for_gestures-master/
```

---

## 3. Build `dataset_36.mat`

```bash
python3 scripts/build_uci_emg_dataset.py \
  --uci-root data/EMG_data_for_gestures-master \
  --out python_ref/HDC-EMG/dataset_36.mat \
  --subjects 1-36
```

Output layout matches Rahimi `dataset.mat`: `COMPLETE_N`, `LABEL_N` for N=1..36.

---

## 4. Quick sanity (~5–10 min)

```bash
python3 python_ref/run_twist2_sweep.py \
  --config python_ref/config/twist2_36_v2_sweep.json \
  --emg-config python_ref/config/emg_baseline_v2.json \
  --quick \
  --out-dir results/protocol_v2/twist2_36_v2_quick
```

---

## 5. Full HDC-2 run @ 128 bits (primary)

```bash
python3 python_ref/run_twist2_sweep.py \
  --config python_ref/config/twist2_36_v2_sweep.json \
  --emg-config python_ref/config/emg_baseline_v2.json \
  --out-dir results/protocol_v2/twist2_36_v2_keep128
```

**Expected runtime:** ~15–20 h (36 subjects × encode train+test + Fisher masks).

**Claim target:** |local oracle − pooled transfer| ≤ **3 pp** on held-out test mean.

---

## 6. Keep-ratio stress grid (issue #2)

Bits @ D=1024: **32, 64, 96, 128, 192, 256**

```bash
bash scripts/run_twist2_36_v2_keep_grid.sh              # all six (~4–5 days total)
bash scripts/run_twist2_36_v2_keep_grid.sh --keep-bits 128   # single point
bash scripts/run_twist2_36_v2_keep_grid.sh --quick      # sanity all six
```

Results root: `results/protocol_v2/twist2_36_v2/keep_{32,64,...}/`

---

## 7. Anchor B density @ 512 bits (optional)

```bash
python3 python_ref/run_twist2_sweep.py \
  --config python_ref/config/twist2_36_v2_keep05_sweep.json \
  --emg-config python_ref/config/emg_baseline_v2.json \
  --out-dir results/protocol_v2/twist2_36_v2_keep512
```

---

## 8. Outputs

Each run writes:

- `twist2_results.json`
- `twist2_summary.csv`
- `README.md`

Key fields: `mean_local_oracle_accuracy`, `mean_pooled_transfer_accuracy`, `mean_gap_local_minus_pooled_pp`, `generalises`.

---

## 9. Compare to legacy HDC-1 runs

| | Protocol | Path | Gap (36-subj mean) |
|---|----------|------|---------------------|
| Legacy | HDC-1 | `results/twist2_36/` | 0.00 pp @ keep=0.125 |
| **New** | **HDC-2** | `results/protocol_v2/twist2_36_v2_*` | TBD |

HDC-1 configs: `twist2_36_sweep.json` + default `emg_baseline.json` (no `--emg-config` override).

5-subject HDC-2 pilot (done): [`results/protocol_v2/twist2_keep0125/`](../results/protocol_v2/twist2_keep0125/) — **+1.02 pp**, generalises.

---

## 10. Optional mask audit

```bash
python3 scripts/twist2_mask_audit_fast.py \
  --out results/protocol_v2/twist2_36_v2_keep128/mask_audit_fast.json
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `dataset not found` | Run step 3; check `python_ref/HDC-EMG/dataset_36.mat` |
| `FileNotFoundError` UCI root | Unzip UCI data under `data/EMG_data_for_gestures-master/` |
| Out of memory | Run one keep point at a time; use `--quick` first |
| Very long runtime | Normal — ~17 h per full keep point on one CPU |
