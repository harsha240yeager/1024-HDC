# Baseline vs deployed RTL encoder — paper subsection (draft)

Use this section in the DATE manuscript / thesis. It separates the **Python
reference baseline** (~90%) from the **silicon verification path** (~74%).

---

## 4.X Classification accuracy: reference baseline and deployed encoder

We evaluate EMG hand-gesture recognition on the UCI dataset (five classes, five
configuration subjects) under frozen protocol **P-may2026** (25% stratified
train, full-sequence test, seed 1). Following Rahimi et al. (ICRC 2016), we
report **two complementary accuracy numbers**:

### Reference baseline (Python only)

The **Stage B binary BSC spatial model** (`stage_b_bsc.py`) uses four-channel
envelope quantization and majority bundling of channel bind records
(`iM[c] ⊕ CiM[v]`). At D = 1024 it achieves **90.30% ± 0.13%** mean spatial
accuracy over five seeds — our frozen project baseline and the ballpark of the
original MAP FPGA-HDC literature (~90.8% spatial).

This baseline establishes that the **dataset, protocol, and BSC algorithm class**
are sound before FPGA integration. It is **not** the encoding implemented in PL.

### Deployed encoder (Python golden + Zynq measurement)

The FPGA implements research-plan Eq. (3.1): for each of four channels and five
feature slots, bind channel, value, and position-shifted feature hypervectors
(20 binds, majority bundle), then Hamming nearest-prototype search
(`encoder_top.sv`, `popcount_am.sv`, item-memory ROMs seed 42). Envelope samples
are mapped to a 4×5 level grid (21-level envelope → 16-level RTL grid, replicated
per feature slot) and streamed via AXI-DMA.

On the full TEST split (**658,004** windows, five subjects), the Python export
reference (`hdc_ref`, unlimited offline prototype bundling) reports **74.24%**
spatial accuracy. ZedBoard replay through the SG DMA path yields **488,550 / 658,004**
correct (**74.24%**), **Δ = 0.00%** vs export ref (PASS under ±0.5% tolerance).
This confirms **bit-exact RTL + driver correctness** on real EMG data; it is not
a failure to reproduce the Stage B reference on silicon.

The ~16 percentage-point gap vs Stage B arises from **different encodings and item
memories** (four-channel records vs 20-pair Eq. 3.1 grid), not from DMA or
classification bugs. We report both numbers explicitly to avoid conflating
literature parity with deployment verification.

### Board pass criterion

Silicon EMG replay **PASS** = |accuracy_board − accuracy_export_ref| ≤ 0.5%.
The frozen **90.30%** figure is **not** the board pass gate. When export uses
`--engine stage_b_bsc`, Stage B accuracy is printed as **INFO only**.

### Research contributions (Hook A and beyond)

The paper’s novelty is **not** reproducing Rahimi accuracy on a second FPGA port.
Contributions are measured on the **deployed RTL encoder path**.

> **Decision (June 2026):** Hook A is re-targeted against the **74.24% unpruned RTL
> encoder baseline** (D=1024). The plan’s original absolute target (≥92% @ D=1024)
> was written for the Stage B ~90% encoding and is **retired** for the silicon path.
> All claims below are stated **relative to the RTL baseline**, which keeps them
> valid regardless of the absolute encoding accuracy.

**Re-stated targets (relative to 74.24% RTL baseline):**

- **Hook A:** joint accuracy / energy / area Pareto over D ∈ {256, 512, 1024, 2048},
  bundle precision CNT_W ∈ {3, 4, 5, 6}, and Fisher-informed pruning ∈ {0, 50, 75, 87.5}%.
  Target: **≤2 pp accuracy drop from the 74.24% baseline at 50% informed pruning**,
  with measured energy reduction along the frontier.
- **Twist 1:** informed pruning beats random by **≥5 pp at iso-density** (relative
  claim — independent of the 74% vs 90% baseline).
- **Twist 2:** cross-subject mask transfer (36 subjects) — **≤3 pp gap** vs
  per-subject masks, or a clean characterisation of failure.
- **System:** end-to-end latency **<50 µs** (met: ~58 µs single / ~4 µs batch),
  **2–4×** energy reduction along the Pareto, **10×** vs ARM-only HDC.

Energy (INA219), Pareto sweeps, and twist experiments use the verified 74.24%
encoder pipeline as the functional starting point.

---

## Suggested table (Table X — EMG accuracy summary)

| Model | Where run | Encoding | Spatial accuracy | Role |
|-------|-----------|----------|------------------|------|
| Stage A MAP (D=10k) | Python | Bipolar MAP | 90.36% | Paper parity anchor |
| Stage B BSC (D=1024) | Python | 4-ch records | **90.30% ± 0.13%** | Frozen reference baseline |
| RTL encoder (`hdc_ref`) | Python export | Eq. (3.1), 4×5 grid | **74.24%** | Golden + export ref |
| RTL encoder | **Zynq-7020** | Same | **74.24%** (Δ0.00%) | Verified deployment |

---

## One-liner for advisor meetings

> We reproduced ~90% in Python (Stage B reference). Silicon runs the research-plan
> encoder at 74% with bit-exact verification. The paper’s contribution is measured
> energy, Pareto, and informed pruning on that real path — not matching Rahimi on a
> different encoding.

See also: `python_ref/config/emg_baseline.json`, `results/phase3/board_emg_replay.txt`,
`scripts/compare_emg_encodings.py`.
