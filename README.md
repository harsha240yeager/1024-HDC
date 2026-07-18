# 1024-HDC — Streaming Hyperdimensional Computing on Zynq

Bit-exact **1024-bit Hyperdimensional Computing (HDC)** in SystemVerilog on Xilinx
Zynq-7020 (ZedBoard), validated with EMG hand-gesture recognition.

**Paper target:** DATE 2027 (~Sep 2026).  
**Repo:** [harsha240yeager/1024-HDC](https://github.com/harsha240yeager/1024-HDC)  
**Manuscript:** [Research-paper](https://github.com/harsha240yeager/Research-paper)  
**Platform:** ZedBoard `xc7z020clg484-1` @ 100 MHz PL · Vivado 2024.2

> **Protocol HDC-2 Tier 1 complete (2026-07-15).** Disjoint train/test split validated;
> silicon EMG replay **72.78%** on **493,512** windows (Δ0.00% vs export ref).
> HDC-1 numbers below (74.24%) are **legacy** — do not cite for generalization.
> See [Protocol HDC-2](#protocol-hdc-2-fix--rerun-plan) · Tier 2+ reruns pending.

---

## Contents

- [Research overview](#research-overview)
- [Protocol HDC-2 fix & rerun plan](#protocol-hdc-2-fix--rerun-plan)
- [Headline results](#headline-results-hdc-1--pending-hdc-2-rerun)
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

## Protocol HDC-2 fix & rerun plan

DATE review identified a **train/test leakage** issue in Protocol HDC-1. This section
documents the problem, the fix, and every experiment that must rerun.

**Tracking:** [`docs/DATE_REVISION_PLAN.md`](docs/DATE_REVISION_PLAN.md) ·
[GitHub issues #1–#11](https://github.com/harsha240yeager/1024-HDC/issues)

### What is wrong (HDC-1)

| Step | HDC-1 behavior | Problem |
|------|----------------|---------|
| Train | First 25% of each class → build **prototypes** + **Fisher mask** | OK |
| Test | **Full** per-subject recording (100% of windows) | Train windows are scored again as “test” |
| Stride-1 | Adjacent windows highly correlated | Inflates apparent test accuracy |

Implementation (`scripts/export_emg_board_vectors.py`):

```python
# HDC-1 — test must NOT stay as q_all after fix
return train_q, train_labels, q_all, labels
```

### What HDC-2 requires

| Rule | Specification |
|------|----------------|
| Train | First 25% of each class per subject (same selection rule) |
| Test | **Remaining 75%** — indices disjoint from train |
| Boundary | Optional ±1 window gap at partition edges |
| Prototypes / Fisher | TRAIN windows only |
| Audit | `train_idx ∩ test_idx = ∅` for every subject |
| Reporting | Per-subject `n_train`, `n_test`, overlap count |

Config (planned): `python_ref/config/emg_baseline_v2.json` · protocol id **`HDC-2`**.

### Code changes (issue #1)

- [x] Rewrite `split_train_test()` — test = complement of train indices
- [x] Add `scripts/audit_split_leakage.py`
- [x] Point sweep configs at `emg_baseline_v2.json`
- [x] Tier 1 rerun + board replay PASS (72.78% silicon)

Fixing `split_train_test()` automatically updates all importers:
`baseline_common.py`, `run_twist1_sweep.py`, `run_twist2_sweep.py`, `run_hook_a_sweep.py`,
`patch_emg_anchor.py`, `regenerate_emg_protos.py`, `export_fisher_pooled.py`.

### Rerun checklist

**Gate:** `python scripts/audit_split_leakage.py` reports overlap **0** before trusting new numbers.

#### Tier 0 — Verify split (~5 min)

```bash
python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline_v2.json
python scripts/export_emg_board_vectors.py --config python_ref/config/emg_baseline_v2.json --max-windows 2000 --summary-only
```

#### Tier 1 — Python + exports (must rerun)

```bash
python python_ref/run_emg_baseline.py --config python_ref/config/emg_baseline_v2.json
python scripts/export_emg_board_vectors.py --config python_ref/config/emg_baseline_v2.json
python scripts/regenerate_emg_protos.py          # pass v2 config when wired
python scripts/export_fisher_pooled.py
python python_ref/run_arm_hdc_baseline.py --emg-config python_ref/config/emg_baseline_v2.json
```

#### Tier 2 — Board / silicon (must rerun; needs ZedBoard)

```bash
bash board/HDC_DMA/build_sw.sh
bash board/HDC_DMA/run_phase3_emg.sh              # main silicon accuracy
python scripts/patch_emg_anchor.py --anchor A && bash board/HDC_DMA/run_anchor_replay.sh A
python scripts/patch_emg_anchor.py --anchor B && bash board/HDC_DMA/run_anchor_replay.sh B
python scripts/patch_emg_anchor.py --anchor C && bash board/HDC_DMA/run_anchor_replay.sh C
```

Bit-exact PASS is vs the **new** HDC-2 export reference (not the old 74.24% golden).

#### Tier 3 — Pruning sweeps (must rerun)

```bash
python python_ref/run_twist1_sweep.py             # + v2 config
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0,1,2,3,4,5,6,7,8,9
python python_ref/run_hook_a_sweep.py
python python_ref/run_twist2_sweep.py
python python_ref/run_twist2_sweep.py --config python_ref/config/twist2_36_sweep.json --out-dir results/twist2_36
python python_ref/plot_results.py --paper
```

#### Does not need rerun

RTL co-simulation (synthetic vectors), OOC D-sweep synthesis, Vivado bitstream — hardware
unchanged. **Hook A / Twist / board accuracy rows do need rerun** (split-dependent).

Energy measurements (PL vs ARM) may stay valid for platform comparison; document
methodology separately ([#8](https://github.com/harsha240yeager/1024-HDC/issues/8)).

### Expected changes after HDC-2

| Quantity | HDC-1 (committed) | HDC-2 (Tier 1 complete) |
|----------|-------------------|-------------------------|
| Test windows | 658,004 (100% of recording) | **493,512** (disjoint 75%) |
| Full-width accuracy | 74.24% silicon | **72.78%** silicon (Δ0.00% vs export) |
| ARM C baseline | 74.15% | **72.65%** |
| Fisher vs random gap | +8.63 / +10.91 pp | **TBD** (Tier 2+) |
| Overlap train∩test | >0 | **0** |

---

## Headline results (HDC-1 — pending HDC-2 rerun)

> **Status:** Numbers in this table are from Protocol **HDC-1**. They remain useful for
> RTL verification (bit-exact replay) but **must be rerun under HDC-2** before paper claims.

| Metric | Value | Evidence |
|--------|-------|----------|
| Silicon EMG replay | **74.24%**, 658k windows, **Δ0.00%** vs golden | [`board_emg_replay.txt`](results/phase3/board_emg_replay.txt) |
| Anchor B / C (pruned) | **72.78%** / **72.85%** (HDC-2) | [`protocol_v2/anchors/`](results/protocol_v2/anchors/) |
| PL batch latency | **~4 µs**/window | Phase 3 SG DMA |
| ARM HDC latency | **819 µs**/window | [`arm_hdc_board_timing.txt`](results/baselines/arm_hdc_board_timing.txt) |
| PL energy (anchor A) | **11.98 ± 0.07 µJ**/w | [`energy_summary.txt`](results/phase3/energy_summary.txt) |
| ARM energy | **2088 ± 6 µJ**/w | same |
| Twist 1 @ keep=0.125 | **+8.63 pp** (informed − random, Python) | [`twist1_keep0125/`](results/twist1_keep0125/) |
| Twist 1 @ keep=0.125 (silicon) | **+10.91 pp** (74.32% vs 63.41% board) | [`twist1_silicon/`](results/phase3/twist1_silicon/) |
| Twist 2 transfer (5-subject pilot) | **+0.86 pp** (local − pooled) | [`twist2/`](results/twist2/) |
| Twist 2 @ 36 UCI (keep=0.125 / 0.5) | **0.00 pp** gap (lossless pruning) | [`twist2_36/`](results/twist2_36/) · [`twist2_36_keep05/`](results/twist2_36_keep05/) |
| PL resources | 35.2k LUT, **0 DSP**, **0 BRAM** | Post-route Phase 3 |

---

## Project status

*July 2026 — **HDC-2 Tier 1 complete** (72.78% silicon); Tier 2+ reruns for DATE.*

| Component | Status |
|-----------|--------|
| RTL + 9 co-sim harnesses | ✅ Bit-exact (unchanged by split fix) |
| Phases 1–3 board bring-up | ✅ EMG PASS under **HDC-2** (72.78%, 493k windows) |
| Hook A | ✅ **HDC-2 complete** (72.65% ref, flat prune to 87.5%) | [`protocol_v2/hook_a/`](results/protocol_v2/hook_a/) |
| Twist 1 / Twist 2 | ✅ HDC-1 numbers — **⏳ rerun under HDC-2** |
| Silicon anchors A/B/C | ✅ **HDC-2 PASS** (72.78% / 72.78% / 72.85%) | [`protocol_v2/anchors/`](results/protocol_v2/anchors/) |
| INA219 energy A/B/C + ARM | ✅ (platform comparison; see issue #8) |
| Protocol HDC-2 disjoint split | ✅ Tier 1 — [#1](https://github.com/harsha240yeager/1024-HDC/issues/1) |
| Cross-subject stress test (keep 32–256) | ⏳ [#2](https://github.com/harsha240yeager/1024-HDC/issues/2) |
| Random baselines + subject-level stats | ⏳ [#3](https://github.com/harsha240yeager/1024-HDC/issues/3) |
| Paper figures | ✅ HDC-1 — refresh after rerun |
| DATE manuscript | ⏳ [Research-paper](https://github.com/harsha240yeager/Research-paper) |

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

### Evaluation protocols

| Protocol | Train | Test | Status |
|----------|-------|------|--------|
| **HDC-1** (`P-may2026`) | First 25% of each class | **Full recording** | ⚠ Leakage — superseded |
| **HDC-2** (planned) | First 25% of each class | **Remaining 75%**, disjoint | ⏳ Issue [#1](https://github.com/harsha240yeager/1024-HDC/issues/1) |

- **Dataset:** UCI EMG hand gestures (Rahimi et al.; fetch `HDC-EMG` separately, GPLv3).
- **Subjects:** S1–S5 (silicon); S1–S36 (Python cross-subject).
- **Metric:** spatial mean accuracy over subjects; board replay uses pooled window accuracy.
- **Config (HDC-1):** [`python_ref/config/emg_baseline.json`](python_ref/config/emg_baseline.json)
- **Config (HDC-2):** `python_ref/config/emg_baseline_v2.json` (when added)

### Verification pipeline

1. **Python golden** (`hdc_ref`) generates expected vectors under the active protocol.
2. **Co-simulation** — nine harnesses, bit-for-bit RTL check (synthetic; not split-dependent).
3. **Board golden** — 200 fixed cases over JTAG.
4. **Full EMG replay** — all TEST windows under active protocol; PASS if
   `|acc_board − acc_ref| ≤ 0.5%` and every label matches the frozen export reference.

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

**Grid:** D × CNT_W × keep_ratio → **64 configs × 5 subjects = 320 rows** (~35 h under HDC-2).

```bash
python3 python_ref/run_hook_a_sweep.py --quick \
  --emg-config python_ref/config/emg_baseline_v2.json \
  --out-dir results/protocol_v2/hook_a
python3 python_ref/run_hook_a_sweep.py \
  --emg-config python_ref/config/emg_baseline_v2.json \
  --out-dir results/protocol_v2/hook_a
```

| Reference | Spatial mean (HDC-2) |
|-----------|----------------------|
| D=1024, CNT_W=6, keep=1.0 (Python) | **72.65%** |
| Board @ keep=1.0 | **72.78%** |
| Best (D=2048, CNT_W≥4) | **76.12%** (OOC only, > device) |
| CNT_W=3 (all D) | **59.48%** (bundle floor) |

**Finding (HDC-2):** at D=1024, CNT_W≥4, informed Fisher pruning is **flat at 72.65%** from 0% to
**87.5%** prune — same iso-accuracy compression pattern as HDC-1, at lower absolute accuracy.

Data: [`protocol_v2/hook_a/sweep_summary.csv`](results/protocol_v2/hook_a/sweep_summary.csv) · HDC-1: [`hook_a/`](results/hook_a/).

### Silicon anchors A/B/C

Same bitstream; only the **global mask** changes. Pooled Fisher · **493,512** HDC-2 test windows each.

| Anchor | keep | Prune | Board | Ref | Δ | PASS |
|--------|------|-------|-------|-----|---|------|
| A | 1.0 | 0% | 72.78% | 72.78% | 0.00% | ✅ |
| B | 0.5 | 50% | 72.78% | 72.78% | 0.00% | ✅ |
| C | 0.125 | 87.5% | 72.84% | 72.85% | 0.00% | ✅ |

**Finding (HDC-2):** A/B flat at 72.78%; C shows a small lift to **72.85%** export ref (128/1024 Fisher bits).

```bash
bash board/HDC_DMA/run_anchor_replay.sh ALL
```

Results: [`results/protocol_v2/anchors/`](results/protocol_v2/anchors/).

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

**36-subject UCI @ keep=0.5 (anchor B, train S1–18 → test S19–36, 2026-07-14):**

```bash
python3 python_ref/run_twist2_sweep.py --config python_ref/config/twist2_36_keep05_sweep.json --out-dir results/twist2_36_keep05
```

| Condition | Accuracy (S19–36 mean) |
|-----------|------------------------|
| Local oracle @ 512 bits | **60.74%** |
| Pooled transfer | **60.74%** |
| **Gap** | **0.00 pp** ✅ (≤3 pp) |

Runtime **~16.9 h**. Same headline as keep=0.125: pruning is **lossless** on every held-out
subject at both densities.

Evidence: [`results/twist2_36_keep05/`](results/twist2_36_keep05/).

#### Why is the 36-subject gap exactly 0.00 pp?

The run is **not** copying one mask into both columns. For each held-out subject the script
builds a **separate local Fisher mask** from that subject's TRAIN windows and compares it to
the **pooled mask** from S1–18 TRAIN (512,487 windows). Prototypes are always per-subject.

| Observation | Meaning |
|-------------|---------|
| `local == unpruned` on all 18 test subjects | Per-subject Fisher pruning is **lossless** @ keep=0.125 and 0.5 |
| `pooled == unpruned` on all 18 test subjects | Pooled cross-subject mask is also **lossless** here |
| ⇒ `local == pooled` | Same accuracy because both masks preserve every TEST decision |
| 5-subject pilot had **+0.86 pp** | When pooled pruning *does* drop bits that matter, the gap is non-zero |

Fast mask audit (masks differ in bit pattern even when accuracy ties):

```bash
python3 scripts/twist2_mask_audit_fast.py
```

Example (S19 @ keep=0.5): **masks not identical**, Jaccard overlap **0.70**, yet 0.00 pp on
subsampled windows — see [`mask_audit_fast.json`](results/twist2_36_keep05/mask_audit_fast.json).

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
| Cross-subject transfer ≤3 pp (pilot + 36 UCI @ keep=0.125 & 0.5) | PL-only Vcc_int power |
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

### Protocol HDC-2 (after issue #1 lands)

```bash
# 0. Audit disjoint split
python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline_v2.json

# 1. Python baselines + export
python python_ref/run_emg_baseline.py --config python_ref/config/emg_baseline_v2.json
python scripts/export_emg_board_vectors.py --config python_ref/config/emg_baseline_v2.json

# 2. Board replay
bash board/HDC_DMA/build_sw.sh && bash board/HDC_DMA/run_phase3_emg.sh

# 3. Pruning sweeps
python python_ref/run_twist1_sweep.py
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0,1,2,3,4
python python_ref/run_hook_a_sweep.py
python python_ref/plot_results.py --paper
```

Full checklist: [Protocol HDC-2 fix & rerun plan](#protocol-hdc-2-fix--rerun-plan).

### Co-simulation (no rerun needed for split fix)

```bash
vsim -c -do sim/run_core_cosim.do
vsim -c -do sim/run_stream_cosim.do
vsim -c -do sim/run_dsweep_cosim.do
```

### Python (Hook A, twists, figures) — HDC-1 commands

> Use `--config python_ref/config/emg_baseline_v2.json` once HDC-2 is implemented.

```bash
cd python_ref && pip install -r requirements.txt
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG   # one-time
python run_smoke_test.py
python run_hook_a_sweep.py --quick
python run_twist1_sweep.py --keep 0.125 --out-dir ../results/twist1_keep0125
python run_twist2_sweep.py
python run_twist2_sweep.py --config config/twist2_36_sweep.json --out-dir ../results/twist2_36
python run_twist2_sweep.py --config config/twist2_36_keep05_sweep.json --out-dir ../results/twist2_36_keep05
python3 ../scripts/twist2_mask_audit_fast.py
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
| `docs/` | Encoder rationale, **[DATE_REVISION_PLAN.md](docs/DATE_REVISION_PLAN.md)**, slides |
| `paper/` | IEEEtran DATE draft skeleton |

HDC-EMG data and co-sim vectors are gitignored — clone dataset and run harnesses to regenerate.

---

## Roadmap

**DATE major revision (post weak-reject review):** see [`docs/DATE_REVISION_PLAN.md`](docs/DATE_REVISION_PLAN.md) · [`docs/DATE_EXECUTION_PLAN.md`](docs/DATE_EXECUTION_PLAN.md) · [GitHub Issues #1–#11](https://github.com/harsha240yeager/1024-HDC/issues)

**Local gate:** `bash scripts/run_hdc2_gate.sh` · **CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

| Phase | Focus | Issue | Status |
|-------|--------|-------|--------|
| **1** | Protocol HDC-2 disjoint split + full rerun | [#1](https://github.com/harsha240yeager/1024-HDC/issues/1) | ⏳ **START HERE** |
| **2** | Cross-subject transfer (keep 32–256 bits) | [#2](https://github.com/harsha240yeager/1024-HDC/issues/2) | ⏳ blocked |
| **3** | Random masks + subject-level stats | [#3](https://github.com/harsha240yeager/1024-HDC/issues/3) | ⏳ blocked |
| **4** | Item-memory seed sensitivity | [#4](https://github.com/harsha240yeager/1024-HDC/issues/4) | ⏳ blocked |
| **5** | Active-bit (257) ablation | [#5](https://github.com/harsha240yeager/1024-HDC/issues/5) | ⏳ blocked |
| **6** | Encoder gap 74% vs 90% | [#6](https://github.com/harsha240yeager/1024-HDC/issues/6) | ⏳ |
| **7** | Claim alignment (Path A/B) | [#7](https://github.com/harsha240yeager/1024-HDC/issues/7) | ⏳ |
| **8** | Energy methodology | [#8](https://github.com/harsha240yeager/1024-HDC/issues/8) | ⏳ |
| **9** | Ranking baselines (variance, MI, …) | [#9](https://github.com/harsha240yeager/1024-HDC/issues/9) | ⏳ blocked |
| **10** | Fix inconsistencies | [#10](https://github.com/harsha240yeager/1024-HDC/issues/10) | ⏳ |
| **11** | Reproducibility artifact | [#11](https://github.com/harsha240yeager/1024-HDC/issues/11) | ⏳ |

**Paper:** [Research-paper issues #1–#4](https://github.com/harsha240yeager/Research-paper/issues) · [`outline.md`](https://github.com/harsha240yeager/Research-paper/blob/main/outline.md)

| Milestone | Status |
|-----------|--------|
| RTL + Phases 1–3 + EMG (Protocol HDC-1) | ✅ superseded by HDC-2 rerun |
| Hook A (HDC-2 Python Pareto) | ✅ 72.65% ref, flat prune | [`protocol_v2/hook_a/`](results/protocol_v2/hook_a/) |
| Twist 1 + Twist 2 (HDC-1) | ✅ pending HDC-2 + new cross-subject design |
| DATE submission | ⏳ Sep 2026 |

---

## License

Project RTL, Python, and docs are original work. EMG dataset/code (Rahimi et al., GPLv3)
must be fetched separately — not redistributed in this repository.
