# 1024-HDC — Streaming Hyperdimensional Computing on Zynq

Bit-exact **1024-bit Hyperdimensional Computing (HDC)** in SystemVerilog on Xilinx
Zynq-7020 (ZedBoard), validated with EMG hand-gesture recognition under frozen protocol
**P-may2026**. The accelerator uses **AXI4-Lite** for configuration and **AXI4-Stream +
DMA** for streaming inference.

**Paper target:** DATE 2027 (~Sep 2026).  
**Repo:** [harsha240yeager/1024-HDC](https://github.com/harsha240yeager/1024-HDC)  
**Platform:** ZedBoard `xc7z020clg484-1` @ 100 MHz PL · Vivado 2024.2

---

## Contents

- [Research overview](#research-overview)
- [Headline results](#headline-results)
- [Project status](#project-status)
- [System architecture](#system-architecture)
- [Methodology](#methodology)
- [Results](#results)
- [Understanding the numbers](#understanding-the-numbers)
- [Paper figures](#paper-figures)
- [Reproduce](#reproduce)
- [Repository layout](#repository-layout)
- [Roadmap](#roadmap)
- [License](#license)

---

## Research overview

### Problem

FPGA implementations of HDC often tune **hypervector dimension** \(D\) to trade accuracy
against area. A separate axis is under-studied: at a **fixed number of kept bits**, *which
positions* should survive pruning?

### Approach

1. Build a **streaming HDC datapath** (bind, permute, bundle, masked Hamming search) with
   a programmable **Fisher-informed pruning mask**.
2. **Verify** RTL bit-for-bit against Python, then replay **658k EMG windows** on silicon.
3. Map **accuracy × area × measured energy** (Hook A) and run two pruning studies:
   - **Twist 1:** informed vs **random** masks at the **same density** (iso-density).
   - **Twist 2:** **cross-subject** mask transfer (train on S1–3, test on S4–5).

### Contributions

| # | Contribution | Main result |
|---|--------------|-------------|
| 1 | **Hook A** — Pareto over \(D\), bundle precision, Fisher keep | Informed prune to **87.5%** is **iso-accuracy** on silicon; PL **~175×** lower energy than ARM |
| 2 | **Twist 1** — bit *position* vs bit *count* | Python **+8.63 pp**; **silicon +10.91 pp** @ 128 bits |
| 3 | **Twist 2** — shared mask across subjects | Pooled mask loses only **+0.86 pp** vs local oracle |

**Important:** The deployment encoder achieves **~74%** spatial accuracy. Literature-class
**~90%** is reproduced in Python with a *different* encoding — see
[Understanding the numbers](#understanding-the-numbers). This is a **systems + pruning**
paper, not an accuracy SOTA claim.

---

## Headline results

| Metric | Value | Evidence |
|--------|-------|----------|
| Silicon EMG replay | **74.24%**, 658k windows, **Δ0.00%** vs golden | [`board_emg_replay.txt`](results/phase3/board_emg_replay.txt) |
| Anchor B / C (pruned) | **74.24%** / **74.32%** (flat vs A) | [`anchors/`](results/phase3/anchors/) |
| PL batch latency | **~4 µs**/window | Phase 3 SG DMA |
| ARM HDC latency | **819 µs**/window | [`arm_hdc_board_timing.txt`](results/baselines/arm_hdc_board_timing.txt) |
| PL energy (anchor A) | **11.98 ± 0.07 µJ**/w | [`energy_summary.txt`](results/phase3/energy_summary.txt) |
| ARM energy | **2088 ± 6 µJ**/w | same |
| Twist 1 @ keep=0.125 | **+8.63 pp** (informed − random, Python) | [`twist1_keep0125/`](results/twist1_keep0125/) |
| Twist 1 @ keep=0.125 (silicon) | **+10.91 pp** (74.32% vs 63.41% board) | [`twist1_silicon/`](results/phase3/twist1_silicon/) |
| Twist 2 transfer | **+0.86 pp** (local − pooled) | [`twist2/`](results/twist2/) |
| PL resources | 35.2k LUT, **0 DSP**, **0 BRAM** | Post-route Phase 3 |

---

## Project status

*July 2026 — experimental work complete; DATE draft in progress.*

| Component | Status |
|-----------|--------|
| RTL + 9 co-sim harnesses | ✅ Bit-exact |
| Phases 1–3 board bring-up | ✅ Golden + EMG PASS |
| Hook A Python sweep (320 rows) | ✅ |
| INA219 energy A/B/C + ARM | ✅ |
| Silicon anchor replays A/B/C | ✅ |
| Twist 1 + Twist 2 (Python + silicon Twist 1) | ✅ |
| Paper figures | ✅ [`results/figures/`](results/figures/) |
| DATE manuscript | ⏳ [`paper/`](paper/) (local / Overleaf) |

---

## System architecture

### Datapath (PL @ 100 MHz)

| Block | Function |
|-------|----------|
| `encoder_top` | EMG window → hypervector (Eq. 3.1 grid, 4×5 binds) |
| `xor_permute_top` | XOR bind + cyclic permute |
| `bundle_unit` | Majority-vote bundling (`CNT_W` bits per counter) |
| `pruning_mask` | Global 1024-bit mask (Fisher-informed keep set) |
| `popcount_am` | Masked Hamming distance + argmin classification |
| `item_mem` | Seed-42 item hypervectors (LUT ROM) |

### Host interface

| Path | Role | Typical latency |
|------|------|-----------------|
| **Phase 1** — AXI4-Lite | Register-mapped infer | ~3 µs/window |
| **Phase 2** — AXI4-Stream | Streaming infer | ~7 µs/window |
| **Phase 3** — SG DMA batch | 200-window batches | **~4 µs/window** amortized |

Phase 3 is the paper inference path: PS loads prototypes/mask; DMA streams windows; PL
returns classifications. Throughput **~216k windows/s** (WNS +0.111 ns @ 100 MHz).

---

## Methodology

### Protocol P-may2026

- **Dataset:** UCI EMG hand gestures (Rahimi et al.; fetch `HDC-EMG` separately, GPLv3).
- **Subjects:** 5 configuration subjects (full train/test splits).
- **Split:** 25% stratified train, full-sequence test, seed 1.
- **Metric:** spatial mean accuracy over subjects.

### Verification pipeline

1. **Python golden** (`hdc_ref`) generates expected vectors.
2. **Co-simulation** — nine harnesses, bit-for-bit RTL check (1k–500 cases each).
3. **Board golden** — 200 fixed cases over JTAG.
4. **Full EMG replay** — 658,004 test windows; PASS if
   `|acc_board − acc_ref| ≤ 0.5%`.

### Fisher pruning mask

Scores each hypervector bit by class separability on TRAIN windows; the **informed mask**
keeps the top fraction (`keep_ratio`). **Random masks** (Twist 1) keep the same number of
bits but at random positions. **Pooled mask** (silicon anchors, Twist 2 train side): one
mask from combined TRAIN data across subjects.

### Energy measurement (INA219)

- **Sense point:** ZedBoard **J21** (10 mΩ), whole-board **12 V** input.
- **Logger:** INA219 on Raspberry Pi (I²C); Ubuntu runs JTAG/bench (two-machine workflow).
- **Integration:** batch mode — energy scaled by measured batch duration (~0.93 ms PL,
  ~164 ms ARM for 200 windows), **not** full 30 s log ÷ 200.
- **Calibration:** [`energy_cal.env`](results/phase3/energy_cal.env) (`SHUNT_MOHM=10`,
  `CAL_REF_MV=2.0`).

Full wiring: [`results/phase3/energy_setup.md`](results/phase3/energy_setup.md).

---

## Results

### RTL co-simulation

| Harness | Cases | Proves |
|---------|-------|--------|
| `run_cosim.do` | 1000 | XOR bind + permute |
| `run_bundle_cosim.do` | 500 | Bundler |
| `run_pruning_mask_cosim.do` | 64 | `pruning_mask.sv` |
| `run_am_cosim.do` | 500 | Masked Hamming AM |
| `run_encoder_cosim.do` | 500 | EMG encoder |
| `run_core_cosim.do` | 500 | End-to-end core |
| `run_core_axi_cosim.do` | 200 | AXI4-Lite |
| `run_stream_cosim.do` | 200 | AXI4-Stream + back-pressure |
| `run_dsweep_cosim.do` | 200/D | D ∈ {256, 512, 1024, 2048} |

### D-sweep (area axis, OOC synthesis)

| D | LUT | Util | WNS | Fmax |
|---|-----|------|-----|------|
| 256 | 7,331 | 13.8% | 1.669 ns | 120 MHz |
| 512 | 14,422 | 27.1% | 1.452 ns | 117 MHz |
| 1024 | 28,600 | 53.8% | 0.781 ns | 109 MHz |
| 2048 | 59,261 | **111%** | 1.340 ns | 116 MHz |

LUT scales ~linearly with \(D\). D=2048 exceeds xc7z020 — Pareto boundary. Reports:
[`results/dsweep/`](results/dsweep/).

### Hook A — accuracy × area × energy

**Grid:** D × CNT_W × keep_ratio → **64 configs × 5 subjects = 320 rows** (~44 h).

```bash
python3 python_ref/run_hook_a_sweep.py --quick
python3 python_ref/run_hook_a_sweep.py
```

| Reference | Spatial mean |
|-----------|--------------|
| D=1024, CNT_W=6, keep=1.0 (Python) | **74.15%** |
| Board @ keep=1.0 | **74.24%** |
| Best (D=2048, CNT_W≥4) | **77.62%** (OOC only, > device) |
| CNT_W=3 (all D) | **59.48%** (bundle floor) |

**Finding:** at D=1024, CNT_W≥4, informed Fisher pruning is **flat at 74.15%** from 0% to
**87.5%** prune — accuracy-neutral compression in Python, confirmed on silicon.

Data: [`hook_a/sweep_summary.csv`](results/hook_a/sweep_summary.csv).

### Silicon anchors A/B/C

Same bitstream; only the **global mask** changes. Pooled Fisher · 658k windows each.

| Anchor | keep | Prune | Board | Ref | Energy (µJ/w) | PASS |
|--------|------|-------|-------|-----|---------------|------|
| A | 1.0 | 0% | 74.24% | 74.24% | 11.98 ± 0.07 | ✅ |
| B | 0.5 | 50% | 74.24% | 74.24% | 11.90 ± 0.04 | ✅ |
| C | 0.125 | 87.5% | 74.32% | 74.32% | 11.81 ± 0.12 | ✅ |

```bash
bash board/HDC_DMA/run_anchor_replay.sh ALL
```

Logs: [`results/phase3/anchors/`](results/phase3/anchors/).

### Measured energy

| Anchor | Path | keep | Static (mW) | Total (µJ/w) | Batch |
|--------|------|------|-------------|--------------|-------|
| A | PL DMA | 1.0 | 2586 ± 17 | **11.98 ± 0.07** | ~0.93 ms / 200 |
| B | PL DMA | 0.5 | 2570 ± 8 | **11.90 ± 0.04** | ~0.93 ms / 200 |
| C | PL DMA | 0.125 | 2551 ± 25 | **11.81 ± 0.12** | ~0.93 ms / 200 |
| ARM | PS SW | 1.0 | 2553 ± 8 | **2088 ± 6** | ~164 ms / 200 |

**Finding:** PL vs ARM ≈ **175×** energy (tracks batch duration). A/B/C energy is **flat**
— pruning reduces effective search width, not measured J21 joules (static-dominated).

Summary: [`energy_summary.txt`](results/phase3/energy_summary.txt) ·
runs: [`energy_runs/anchor_*/`](results/phase3/energy_runs/).

### Twist 1 — informed vs random (iso-density)

Same kept-bit count; only mask selection differs. Five random seeds per subject.

```bash
python3 python_ref/run_twist1_sweep.py
python3 python_ref/run_twist1_sweep.py --keep 0.125 --out-dir results/twist1_keep0125
```

| keep | Bits kept | Informed | Random (mean) | Gap |
|------|-----------|----------|---------------|-----|
| 0.5 | 512 | 74.15% | 72.44% ± 1.57 pp | **+1.70 pp** |
| **0.125** | **128** | **74.15%** | **65.51% ± 2.85 pp** | **+8.63 pp** ✅ |

At aggressive compression, **which bits** you keep matters: informed preserves accuracy;
random collapses. Headline figure: [`twist1_informed_vs_random_keep0125.png`](results/figures/twist1_informed_vs_random_keep0125.png).

**Silicon (ZedBoard, pooled mask @ keep=0.125, 658k windows, 2026-07-13):**

```bash
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0
```

| Condition | Board accuracy |
|-----------|----------------|
| Fisher informed (anchor C) | **74.32%** |
| Random iso-density (seed 0) | **63.41%** |
| **Gap** | **+10.91 pp** ✅ (PASS, Δ0.00% vs export ref) |

Evidence: [`results/phase3/twist1_silicon/`](results/phase3/twist1_silicon/).

### Twist 2 — cross-subject mask transfer

Mask from S1–3 TRAIN (106,379 windows) → test S4–5 with **own prototypes**.

```bash
python3 python_ref/run_twist2_sweep.py
```

| Condition | Accuracy (S4+S5 mean) |
|-----------|------------------------|
| Local oracle @ 128 bits | **69.31%** |
| Pooled transfer | **68.45%** |
| **Gap** | **+0.86 pp** ✅ (≤3 pp) |

A single shared mask generalises without per-user mask calibration (within P-may2026).

**36-subject UCI (train S1–18 → test S19–36, 2026-07-13):**

```bash
python3 scripts/build_uci_emg_dataset.py
python3 python_ref/run_twist2_sweep.py --config python_ref/config/twist2_36_sweep.json --out-dir results/twist2_36
```

| Condition | Accuracy (S19–36 mean) |
|-----------|------------------------|
| Local oracle @ 128 bits | **60.74%** |
| Pooled transfer | **60.74%** |
| **Gap** | **0.00 pp** ✅ (≤3 pp) |

Runtime **~16.8 h** (~5.0M encodes). Pruning @ keep=0.125 is lossless on all held-out
subjects. UCI `dataset_36.mat` uses a separate preprocessing path from the Rahimi 5-subject
board dataset — absolute accuracy is not directly comparable to the 69% pilot.

Evidence: [`results/twist2_36/`](results/twist2_36/) ·
figure [`twist2_cross_subject_36.png`](results/figures/twist2_cross_subject_36.png).

### Deployment baselines

| Path | Accuracy | Latency | Energy |
|------|----------|---------|--------|
| **PL DMA batch** | 74.24% | ~4 µs/w | 11.98 µJ/w |
| **ARM HDC** | 74.15% | 819 µs/w | 2088 µJ/w |
| Tiny int8 MLP | 93.0% | — | — |

MLP is higher accuracy but a **trained dense network** — different deployment class from
fixed-logic streaming HDC. Details: [`results/baselines/`](results/baselines/).

---

## Understanding the numbers

### Two accuracy baselines (do not conflate)

| Track | Encoding | Accuracy | Role |
|-------|----------|----------|------|
| Stage B (Python) | 4-channel records | **~90.30%** | Literature parity |
| **RTL + silicon** | Eq. 3.1 grid | **74.24%** | **Verified deployment path** |

The ~16 pp gap is **different encoders**, not a board bug. Silicon PASS is Δ0.00% vs the
RTL golden. Full write-up: [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md).

### How to read energy

| What we report | Meaning |
|----------------|---------|
| Total µJ/window | Batch-amortized **system** energy @ 12 V |
| PL ~12 µJ/w | Dominated by **static power** over short PL batch slot |
| Flat A/B/C | Pruning does **not** cut board joules in this setup |
| PL vs ARM ~175× | Real efficiency win (duration + static) |

Do **not** use legacy full-log integration (~2240 µJ/w) — wrong ~190×.

### What the paper claims — and does not

| ✅ Claims | ❌ Does not claim |
|----------|------------------|
| Bit-exact verified streaming HDC on Zynq | Matching ~90% on FPGA |
| Iso-accuracy informed pruning to 87.5% | Pruning reduces measured J21 µJ |
| Informed ≫ random at 128 bits (Python + silicon) | Beating 93% MLP |
| Cross-subject transfer ≤3 pp (pilot + 36 UCI) | PL-only Vcc_int power |
| PL ~175× lower energy than ARM SW | |

---

## Paper figures

```bash
python3 python_ref/plot_results.py              # 300 dpi PNG + vector PDF
python3 python_ref/plot_results.py --dpi 600    # extra-high rasterization
```

| Figure | Content |
|--------|---------|
| [`hookA_pareto_measured.png`](results/figures/hookA_pareto_measured.png) | Main Pareto + measured µJ |
| [`fisher_heatmap.png`](results/figures/fisher_heatmap.png) | Fisher scores + mask cutoffs |
| [`twist1_informed_vs_random_keep0125.png`](results/figures/twist1_informed_vs_random_keep0125.png) | Twist 1 headline |
| [`twist2_cross_subject.png`](results/figures/twist2_cross_subject.png) | Twist 2 pilot (S1–3 → S4–5) |
| [`twist2_cross_subject_36.png`](results/figures/twist2_cross_subject_36.png) | Twist 2 @ 36 UCI subjects |
| [`baselines_bar.png`](results/figures/baselines_bar.png) | PL vs ARM vs MLP |

Index: [`results/figures/README.md`](results/figures/README.md). LaTeX draft: [`paper/main.tex`](paper/main.tex).

---

## Reproduce

### Co-simulation

```bash
vsim -c -do sim/run_core_cosim.do
vsim -c -do sim/run_stream_cosim.do
vsim -c -do sim/run_dsweep_cosim.do
```

### Python (Hook A, twists, figures)

```bash
cd python_ref && pip install -r requirements.txt
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG   # one-time
python run_smoke_test.py
python run_hook_a_sweep.py --quick
python run_twist1_sweep.py --keep 0.125 --out-dir ../results/twist1_keep0125
python run_twist2_sweep.py
python run_twist2_sweep.py --config config/twist2_36_sweep.json --out-dir ../results/twist2_36
python plot_results.py
```

### ZedBoard

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
cd board/HDC_DMA && bash build_sw.sh
bash run_phase3_bench.sh
bash run_phase3_emg.sh
bash run_anchor_replay.sh ALL
bash run_twist1_board.sh --random-seeds 0
```

### Energy (optional re-measure; results already committed)

```bash
source results/phase3/energy_cal.env
bash scripts/run_energy_only.sh
```

Pi + INA219 are **not required** for analysis or paper writing — only to re-run measurements.

---

## Repository layout

| Path | Role |
|------|------|
| `rtl/`, `tb/`, `sim/` | Datapath, testbenches, co-sim harnesses |
| `sw/` | Bare-metal + ARM HDC baseline |
| `python_ref/` | Golden model, Hook A / Twist runners, `plot_results.py` |
| `board/HDC_DMA/` | Vitis workspace, JTAG, anchor replay |
| `scripts/` | Golden prep, energy campaign, UCI dataset builder, `patch_emg_anchor.py` |
| `results/` | All committed measurements and figures |
| `docs/` | Encoder rationale, research plan, slides |
| `paper/` | IEEEtran DATE draft skeleton |

HDC-EMG data and co-sim vectors are gitignored — clone dataset and run harnesses to regenerate.

---

## Roadmap

| Milestone | Status |
|-----------|--------|
| RTL + Phases 1–3 + EMG | ✅ |
| Hook A + energy + anchors | ✅ |
| Twist 1 + Twist 2 + figures (incl. silicon Twist 1) | ✅ |
| DATE draft | ⏳ Sep 2026 |

---

## License

Project RTL, Python, and docs are original work. EMG dataset/code (Rahimi et al., GPLv3)
must be fetched separately — not redistributed in this repository.
