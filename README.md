# 1024-HDC — Streaming Hyperdimensional Computing on Zynq

A **1024-bit Hyperdimensional Computing (HDC)** classifier in SystemVerilog for the
Xilinx Zynq-7020 (ZedBoard). The design is **bit-exact** against a Python golden
model and validated on silicon with EMG hand-gesture recognition under frozen
protocol **P-may2026**.

**Working title (DATE 2027):** *Informed Bit-Position Pruning for Streaming
Hyperdimensional Computing on Zynq — A Verified Silicon Study of Accuracy, Energy,
and Cross-Subject Mask Transfer.*

---

## Why this project

Prior FPGA-HDC work often varies hypervector **dimension** \(D\). This project asks a
different question: at **fixed density**, *which bit positions* matter?

| Question | Experiment | Answer (measured) |
|----------|------------|-------------------|
| Can we prune aggressively without losing accuracy? | Hook A + silicon anchors A/B/C | **Yes** — informed Fisher pruning is iso-accuracy to **87.5%** prune |
| Do bit *positions* matter, or only bit *count*? | Twist 1 (informed vs random) | **Yes** — at 128 bits, informed beats random by **+8.63 pp** |
| Can one mask serve multiple subjects? | Twist 2 (cross-subject transfer) | **Yes** — pooled mask loses only **+0.86 pp** vs local oracle |
| Is PL worth it vs ARM software HDC? | Latency + INA219 energy | **~200×** faster · **~175×** lower energy per window |

All claims are relative to the **verified RTL encoder path (~74%)**, not a re-port of
literature ~90% accuracy (different encoding — see [two-baseline story](#accuracy-the-two-baseline-story)).

**Platform:** ZedBoard `xc7z020clg484-1` @ 100 MHz PL · Vivado 2024.2 · ModelSim/Questa  
**Repo:** [harsha240yeager/1024-HDC](https://github.com/harsha240yeager/1024-HDC)

---

## Contents

- [At a glance](#at-a-glance)
- [What the hardware does](#what-the-hardware-does)
- [Status](#status)
- [Results](#results)
  - [RTL verification](#rtl-verification-co-simulation)
  - [Board bring-up](#board-bring-up--phases-13)
  - [EMG replay on silicon](#emg-full-dataset-replay-on-silicon)
  - [D-sweep area](#d-sweep--area-axis)
  - [Hook A Pareto](#hook-a--accuracy--area--energy-pareto)
  - [Silicon anchors A/B/C](#silicon-anchors-abc--pruning-on-board)
  - [Measured energy](#measured-energy--pl-vs-arm)
  - [Twist 1](#twist-1--informed-vs-random-at-iso-density)
  - [Twist 2](#twist-2--cross-subject-mask-transfer)
  - [Comparison baselines](#comparison-baselines)
  - [Paper figures](#paper-figures)
- [Accuracy: the two-baseline story](#accuracy-the-two-baseline-story)
- [How to read the energy numbers](#how-to-read-the-energy-numbers)
- [Limitations](#limitations)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Energy measurement setup](#energy-measurement-setup)
- [Paper draft](#paper-draft)
- [Roadmap](#roadmap)
- [License](#license)

---

## At a glance

| Metric | Value | Where |
|--------|-------|--------|
| Board accuracy (658k windows) | **74.24%**, Δ0.00% vs golden | Phase 3 EMG replay |
| Anchor B / C board accuracy | **74.24%** / **74.32%** (flat vs prune) | Silicon anchors |
| PL batch latency | **~4 µs**/window | Phase 3 SG DMA |
| ARM HDC latency | **819 µs**/window | Cortex-A9 |
| PL energy (anchor A) | **11.98 ± 0.07 µJ**/window | INA219 @ J21 |
| ARM energy | **2088 ± 6 µJ**/window | Same setup |
| Twist 1 gap @ keep=0.125 | **+8.63 pp** (informed − random) | Python, 5 subjects |
| Twist 2 transfer gap | **+0.86 pp** (local − pooled) | S1–3 → S4–5 |
| Resources (DMA path) | 35.2k LUT · 0 DSP · 0 BRAM | Post-route |

---

## What the hardware does

Binary Spatter Code HDC on 1024-bit hypervectors:

| Primitive | Role |
|-----------|------|
| **XOR bind** | Combine channel / value / position symbols |
| **Permute** | Cyclic shift for positional encoding |
| **Majority bundle** | Form class prototypes (bundle precision `CNT_W`) |
| **Masked Hamming AM** | Nearest-prototype search; Fisher **pruning mask** zeros unused bits |

Control: **AXI4-Lite** from the PS (prototypes, mask, config).  
Data path: **AXI4-Stream + DMA** at inference rate (batch SG for throughput).

---

## Status

*Last updated: July 2026.*

**Experimental work is complete.** Remaining: DATE paper draft (`paper/`).

| Area | State |
|------|-------|
| RTL + 9 co-sim harnesses + `pruning_mask` | ✅ Bit-exact vs Python |
| D-sweep cosim + OOC synth — D ∈ {256, 512, 1024, 2048} | ✅ [`results/dsweep/`](results/dsweep/) |
| Phase 1 — AXI-Lite | ✅ 200/200 golden · ~3 µs/window |
| Phase 2 — AXI-DMA stream | ✅ 200/200 golden · ~7 µs/window |
| Phase 3 — SG batch + EMG replay | ✅ ~216k win/s · **74.24%** · 658k windows |
| Hook A — Python sweep (D × CNT_W × pruning) | ✅ 64 configs × 5 subjects (320 rows) |
| INA219 energy — A/B/C + ARM | ✅ PL **~12 µJ/w** · ARM **~2088 µJ/w** |
| Silicon EMG anchors A/B/C | ✅ **74.24–74.32%**, flat vs prune |
| ARM HDC + tiny MLP baselines | ✅ Accuracy · latency · (ARM) energy |
| Twist 1 @ keep=0.5 / 0.125 | ✅ **+1.70 pp** / **+8.63 pp** |
| Twist 2 — cross-subject transfer | ✅ **+0.86 pp**, generalises |
| Paper figures | ✅ [`results/figures/`](results/figures/) |
| DATE draft | ⏳ [`paper/`](paper/) |

---

## Results

All board numbers: ZedBoard `xc7z020clg484-1` @ 100 MHz PL (Vivado 2024.2).  
Raw logs and CSVs: [`results/`](results/).

### RTL verification (co-simulation)

Each harness checks RTL **bit-for-bit** against the Python golden reference.

| Harness | Cases | Proves |
|---------|-------|--------|
| `run_cosim.do` | 1000 | XOR bind + permute |
| `run_bundle_cosim.do` | 500 | Majority bundler |
| `run_pruning_mask_cosim.do` | 64 | `pruning_mask.sv` (full + AXI writes) |
| `run_am_cosim.do` | 500 | Masked Hamming AM + argmin |
| `run_encoder_cosim.do` | 500 | EMG window encoder |
| `run_core_cosim.do` | 500 | End-to-end encode → classify |
| `run_core_axi_cosim.do` | 200 | AXI4-Lite programming |
| `run_stream_cosim.do` | 200 | AXI4-Stream + back-pressure |
| `run_dsweep_cosim.do` | 200/D | Core at D ∈ {256, 512, 1024, 2048} |

### Board bring-up — Phases 1–3

| | Phase 1 — AXI-Lite | Phase 2 — DMA | Phase 3 — SG batch |
|--|--------------------|---------------|---------------------|
| Role | Register-mapped baseline | Streaming path | Throughput + golden |
| Golden | 200/200 | 200/200 | 200/200 |
| Latency | 3 µs/w | 7 µs/w | 58 µs single · **~4 µs/w batch** |
| Throughput | ~333k win/s | ~143k win/s | **~216k win/s** |
| WNS @ 100 MHz | +0.246 ns | +0.023 ns | +0.111 ns |

Post-route utilisation (Phase 2/3 DMA path): **35,206 LUT (66.2%)**, **27,639 FF**,
**0 DSP**, **0 BRAM** — pure-logic accelerator; `item_mem` as LUT ROM.

### EMG full-dataset replay on silicon

| Metric | Value |
|--------|-------|
| Windows (5 subjects, full TEST) | 658,004 |
| Correct | 488,550 |
| Board accuracy | **74.24%** |
| Python export-ref | 74.24% |
| Board vs golden | **Δ0.00%** → PASS (±0.5% gate) |

Evidence: [`results/phase3/board_emg_replay.txt`](results/phase3/board_emg_replay.txt).  
This is the verification cornerstone: silicon reproduces the golden model over real EMG.

### D-sweep — area axis

Core-only out-of-context synthesis (Vivado 2024.2). Full reports: [`results/dsweep/`](results/dsweep/).

| D | Slice LUT | LUT util | WNS (ns) | Fmax | Cosim |
|---|-----------|----------|----------|------|-------|
| 256 | 7,331 | 13.8% | 1.669 | 120 MHz | PASS |
| 512 | 14,422 | 27.1% | 1.452 | 117 MHz | PASS |
| 1024 | 28,600 | 53.8% | 0.781 | 109 MHz | PASS |
| 2048 | 59,261 | **111%** | 1.340 | 116 MHz | PASS |

LUT/FF scale ~linearly with \(D\). **D=1024** is timing-tightest but meets 100 MHz.
**D=2048** exceeds the xc7z020 OOC LUT budget — a reportable Pareto boundary.

### Hook A — accuracy × area × energy Pareto

**Goal:** map the three-axis trade-off surface for the *deployed* RTL encoder.

- Engine: RTL-matched `hdc_ref` · protocol **P-may2026** · 5 subjects  
- Masks: informed Fisher (per-subject in Python sweep)  
- Grid: **D** ∈ {256, 512, 1024, 2048} × **CNT_W** ∈ {3, 4, 5, 6} × **keep** ∈ {1.0, 0.5, 0.25, 0.125}  
- Outputs: [`results/hook_a/sweep_summary.csv`](results/hook_a/sweep_summary.csv) (320 rows, ~44 h)

```bash
python3 python_ref/run_hook_a_sweep.py --quick   # ~3 min
python3 python_ref/run_hook_a_sweep.py           # full grid
```

**Headline (5-subject spatial mean, informed Fisher):**

| Reference | Accuracy |
|-----------|----------|
| D=1024, CNT_W=6, keep=1.0 (Python) | **74.15%** |
| Board RTL EMG replay (keep=1.0) | **74.24%** |
| Best grid point (D=2048, CNT_W≥4) | **77.62%** (59k LUT — OOC only) |
| CNT_W=3 (all D) | **59.48%** (bundle-precision floor) |

At **D=1024, CNT_W≥4**, informed pruning is **flat at 74.15%** from 0% → **87.5%** prune.
Silicon confirms flat accuracy at anchors A/B/C (**74.24–74.32%**). Measured board energy
at those anchors is also **flat ~12 µJ/w** — pruning buys **area / bit-count**, not J21 joules
(static-dominated; see [energy explanation](#how-to-read-the-energy-numbers)).

Full table: [`results/hook_a/README.md`](results/hook_a/README.md).  
Pareto figure: [`results/figures/hookA_pareto_measured.png`](results/figures/hookA_pareto_measured.png).

### Silicon anchors A/B/C — pruning on board

Same Phase 3 bitstream; only the **global pruning mask** is reprogrammed.
Pooled Fisher mask · 658,004 windows each · PASS = |board − export ref| ≤ 0.5%.

| Anchor | keep | Prune | Board acc | Export ref | Energy (µJ/w) | PASS |
|--------|------|-------|-----------|------------|---------------|------|
| **A** — baseline | 1.0 | 0% | **74.24%** | 74.24% | 11.98 ± 0.07 | ✅ Δ0.00% |
| **B** — knee | 0.5 | 50% | **74.24%** | 74.24% | 11.90 ± 0.04 | ✅ Δ0.00% |
| **C** — aggressive | 0.125 | 87.5% | **74.32%** | 74.32% | 11.81 ± 0.12 | ✅ Δ0.00% |

```bash
bash board/HDC_DMA/run_anchor_replay.sh ALL   # A → B → C
```

**Mask note:** Hook A Python uses **per-subject** Fisher masks; silicon uses one **pooled**
Fisher mask. At keep=1.0 both are all-ones; at B/C bit patterns can differ. Board PASS is
vs the *patched* export reference for that mask — and all three anchors passed.

Evidence: [`results/phase3/anchors/`](results/phase3/anchors/).

### Measured energy — PL vs ARM

Whole-board **12 V** at ZedBoard **J21** (10 mΩ) + INA219 · batch integration · **n=3** each ·
2026-07-02. Summary: [`results/phase3/energy_summary.txt`](results/phase3/energy_summary.txt).

| Anchor | Path | keep | Static (mW) | Total (µJ/w) | Batch slot |
|--------|------|------|-------------|--------------|------------|
| **A** | PL DMA | 1.0 | 2586 ± 17 | **11.98 ± 0.07** | ~0.93 ms / 200 win |
| **B** | PL DMA | 0.5 | 2570 ± 8 | **11.90 ± 0.04** | ~0.93 ms / 200 win |
| **C** | PL DMA | 0.125 | 2551 ± 25 | **11.81 ± 0.12** | ~0.93 ms / 200 win |
| **ARM** | PS software | 1.0 | 2553 ± 8 | **2088 ± 6** | ~164 ms / 200 win |

**Takeaway:** PL vs ARM ≈ **175×** lower energy (tracks batch duration ratio). Pruning does
**not** reduce measured PL µJ/w — A/B/C are flat within noise.

### Twist 1 — informed vs random at iso-density

**Claim:** *bit position matters, not only bit count.*

Same \(D{=}1024\), CNT_W=6 · per-subject Fisher from TRAIN · TEST evaluation · **five random
seeds** per subject · **identical kept-bit count** as the informed mask.

```bash
python3 python_ref/run_twist1_sweep.py                    # keep=0.5
python3 python_ref/run_twist1_sweep.py --keep 0.125 \
  --out-dir results/twist1_keep0125                       # headline
```

**@ keep=0.5 (512 bits) — supplementary:**

| Mask | Spatial mean |
|------|--------------|
| Fisher informed | **74.15%** |
| Random (mean ± std) | **72.44% ± 1.57 pp** |
| **Gap** | **+1.70 pp** |

**@ keep=0.125 (128 bits) — headline novelty:**

| Mask | Spatial mean |
|------|--------------|
| Fisher informed | **74.15%** (lossless vs unpruned) |
| Random (mean ± std) | **65.51% ± 2.85 pp** |
| **Gap** | **+8.63 pp** ✅ (≥5 pp target) |

Per-subject gap @ keep=0.125: S1 +7.2 · S2 **+13.0** · S3 **+12.3** · S4 +3.5 · S5 +7.2 pp.

**Interpretation:** Hook A shows informed pruning is accuracy-neutral. Twist 1 shows that
**random** masks of the same density collapse at aggressive compression — selection quality
is the contribution.

Evidence: [`results/twist1/`](results/twist1/) · [`results/twist1_keep0125/`](results/twist1_keep0125/) ·
figure [`twist1_informed_vs_random_keep0125.png`](results/figures/twist1_informed_vs_random_keep0125.png).

### Twist 2 — cross-subject mask transfer

**Claim:** a *shared* Fisher mask can transfer across subjects without per-user recalibration.

- Train mask on TRAIN windows of subjects **{1, 2, 3}** (106,379 windows)  
- Evaluate on TEST of held-out **{4, 5}**  
- Each test subject keeps **own prototypes** — only the mask is transferred  
- Density: keep=0.125 (128 bits) · **full** P-may2026 windows (not capped)

```bash
python3 python_ref/run_twist2_sweep.py
```

| Condition | Spatial mean (S4+S5) |
|-----------|----------------------|
| Unpruned / local oracle @ 128 bits | **69.31%** |
| Pooled transfer (mask from S1–3) | **68.45%** |
| **Gap (local − pooled)** | **+0.86 pp** ✅ (≤3 pp → generalises) |

Per subject: S4 +0.63 pp · S5 +1.09 pp.

Evidence: [`results/twist2/`](results/twist2/) ·
figure [`twist2_cross_subject.png`](results/figures/twist2_cross_subject.png).

### Comparison baselines

Same **P-may2026** protocol. Details: [`results/baselines/`](results/baselines/).

| Baseline | Accuracy | Latency | Energy (12 V, J21) |
|----------|----------|---------|---------------------|
| **PL DMA batch** | **74.24%** | ~4 µs/window | **11.98 ± 0.07 µJ/w** |
| **ARM HDC** (`hdc_arm_ref.c`) | 74.15% | **819 µs**/window | **2088 ± 6 µJ/w** |
| Tiny int8 MLP (~5.8k params) | 93.01% / 92.99% int8 | — | — |
| AXI-Lite PL path | — | ~3 µs/window | — |

PL vs ARM: **~200×** latency · **~175×** energy (batch amortized, n=3).  
The MLP is a higher-accuracy NN reference — different deployment class (trained dense net vs
fixed-logic streaming HDC).

Runners: [`run_arm_hdc_baseline.py`](python_ref/run_arm_hdc_baseline.py),
[`run_mlp_baseline.py`](python_ref/run_mlp_baseline.py),
[`run_baselines.py`](python_ref/run_baselines.py).

### Paper figures

Regenerate all static PNG/PDF from committed results:

```bash
python3 python_ref/plot_results.py
```

| Figure | Role |
|--------|------|
| [`hookA_pareto_measured.png`](results/figures/hookA_pareto_measured.png) | Main Hook A Pareto + measured µJ |
| [`fisher_heatmap.png`](results/figures/fisher_heatmap.png) | Fisher scores + mask cutoffs |
| [`twist1_informed_vs_random_keep0125.png`](results/figures/twist1_informed_vs_random_keep0125.png) | Twist 1 headline (+8.6 pp) |
| [`twist2_cross_subject.png`](results/figures/twist2_cross_subject.png) | Twist 2 transfer |
| [`baselines_bar.png`](results/figures/baselines_bar.png) | PL vs ARM vs MLP |
| [`hookA_pruning.png`](results/figures/hookA_pruning.png) | Acc + energy proxy vs prune % |

Index: [`results/figures/README.md`](results/figures/README.md).

---

## Accuracy: the two-baseline story

This project reports **two accuracy families on purpose** — they answer different questions.

| Track | Where | Encoding | Accuracy | Role |
|-------|-------|----------|----------|------|
| Stage A — MAP parity | Python | Bipolar MAP, D=10k | 90.36% | Literature parity |
| Stage B — BSC reference | Python | 4-channel records | 90.30% ± 0.13 | Frozen baseline @ D=1024 |
| **RTL encoder** | Python + **ZedBoard** | Eq. (3.1) 4×5 grid | **74.24%** | **Verified deployment path** |

The silicon runs a *hardware-faithful* encoder (Eq. 3.1 grid, seed-42 item memory), not
Rahimi’s spatial-record encoding — matching ~90% on FPGA was never the goal. The
deliverable is:

1. **Verification fidelity** — board = golden to Δ0.00% over 658k windows  
2. **Systems study** — throughput, area, measured energy, informed pruning  

All Hook A / Twist / energy claims are **relative to the 74.24% RTL baseline**.

Full rationale: [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md).  
Silicon PASS gate: `|board_acc − export_ref| ≤ 0.5%`.

---

## How to read the energy numbers

| Metric | Meaning |
|--------|---------|
| Static power | Whole board @ 12 V (J21), PL programmed, idle |
| Total µJ/window | ≈ `P_static × t_batch / 200` (batch-amortized system energy) |
| Dynamic increment | Above-idle during burst — **noisy** at 100 Hz vs ~926 µs PL burst |

**Claimed:** system amortized energy at batch throughput; PL vs ARM efficiency; 3-run
repeatability.  
**Not claimed:** “PL dynamic switching = 12 µJ” or “pruning cuts board joules.”

Legacy full-log integration (~2240 µJ/w) was wrong ~190× — use `--integrate-mode batch` only.

Wiring and procedure: [Energy measurement setup](#energy-measurement-setup).

---

## Limitations

| Topic | Note |
|-------|------|
| PL total energy | Static-dominated; pruning cuts **area/bits**, not measured J21 µJ/w |
| Dynamic increment | Burst undersampled @ 100 Hz — not a headline metric |
| Measurement scope | Whole-board 12 V @ J21, not Vcc_int-only PL rail |
| Hook A energy | 64 Python configs; **four measured** silicon points (A/B/C/ARM) |
| Subjects | Five configuration subjects throughout (P-may2026) |
| Twist 1 density | ≥5 pp target met at keep=0.125; smaller gap (+1.7 pp) at keep=0.5 |
| 74% vs ~90% | Different encoder by design — see [two-baseline story](#accuracy-the-two-baseline-story) |
| Fisher masks | Python Hook A: per-subject; silicon: pooled — board matched export ref at all anchors |
| vs MLP (~93%) | Higher accuracy, different class (trained NN vs fixed streaming HDC) |

---

## Repository layout

| Path | Contents |
|------|----------|
| `rtl/` | Datapath: bind, permute, bundle, `pruning_mask`, AM, encoder, AXI wrappers |
| `sim/` | One-command co-sim harnesses (`run_*_cosim.do`) |
| `tb/` | Self-checking + co-sim testbenches |
| `sw/` | Bare-metal drivers, `hdc_arm_ref.c`, `hdc_arm_bench.c` |
| `python_ref/` | Golden model, Hook A / Twist runners, baselines, `plot_results.py` |
| `scripts/` | Golden prep, energy campaign, `ina219_log.py`, `patch_emg_anchor.py` |
| `board/HDC_DMA/` | Vitis workspace, JTAG scripts, anchor / energy loaders |
| `results/` | Phase logs, Hook A, twists, energy, anchors, figures |
| `docs/` | Research plan, encoder rationale, presentation |
| `paper/` | IEEEtran DATE draft skeleton (`main.tex`) |

Third-party HDC-EMG data (`python_ref/HDC-EMG/`, GPLv3) and generated co-sim vectors are
**not** committed — reproducible via clone + harnesses.

---

## Quick start

### RTL co-simulation

```bash
vsim -c -do sim/run_core_cosim.do
vsim -c -do sim/run_stream_cosim.do
vsim -c -do sim/run_dsweep_cosim.do
vivado -mode batch -source scripts/dsweep_synth.tcl
```

### Python golden, Hook A, Twists

```bash
cd python_ref && pip install -r requirements.txt
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG   # one-time

python run_smoke_test.py
python run_hook_a_sweep.py --quick
python run_twist1_sweep.py --keep 0.125 --out-dir ../results/twist1_keep0125
python run_twist2_sweep.py
python plot_results.py
```

### ZedBoard Phase 3

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
cd board/HDC_DMA && bash build_sw.sh
bash run_phase3_bench.sh
bash run_phase3_emg.sh
bash run_anchor_replay.sh ALL
```

### Energy campaign (optional re-measure)

Pi + INA219 are **not required** for remaining paper work — results are already committed.
To re-run:

```bash
source results/phase3/energy_cal.env
bash scripts/run_energy_only.sh
```

---

## Energy measurement setup

**Hardware:** ZedBoard J20 (12 V barrel) · J21 current sense (10 mΩ) · INA219 · Raspberry Pi I²C.  
Ubuntu host runs JTAG/bench — **two-machine** workflow.

```text
12 V adapter → J20                  Pi 3.3V → INA219 VCC
J21 pin 1 → INA219 Vin+             Pi SDA/SCL → INA219
J21 pin 2 → INA219 Vin−             Common GND (Pi + ZedBoard)
```

**Calibration:** `source results/phase3/energy_cal.env` (`SHUNT_MOHM=10`, `CAL_REF_MV=2.0`).

Full wiring and safety: [`results/phase3/energy_setup.md`](results/phase3/energy_setup.md).

| Script | Role |
|--------|------|
| [`run_energy_only.sh`](scripts/run_energy_only.sh) | Full A→B→C→ARM campaign (3× each) |
| [`run_energy_one_run.sh`](scripts/run_energy_one_run.sh) | Single run |
| [`run_phase3_bench_load_energy.sh`](board/HDC_DMA/run_phase3_bench_load_energy.sh) | PL bench trigger |
| [`run_arm_bench_load_energy.sh`](board/HDC_DMA/run_arm_bench_load_energy.sh) | ARM bench trigger |
| [`patch_emg_anchor.py`](scripts/patch_emg_anchor.py) | Reprogram Fisher mask |

---

## Paper draft

IEEEtran skeleton for DATE:

```text
paper/
  main.tex      # title, abstract, section stubs, figure includes
  refs.bib      # starter bibliography
  outline.md    # section checklist
  README.md     # build instructions
```

```bash
cd paper && pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

On Overleaf: upload figures into `figures/` and set `\graphicspath{{figures/}}`.

---

## Roadmap

| Milestone | Status |
|-----------|--------|
| RTL + cosim + Phases 1–3 | ✅ |
| Hook A Python sweep | ✅ |
| INA219 energy A/B/C + ARM | ✅ |
| Silicon EMG anchors A/B/C | ✅ |
| Twist 1 (@ 0.5 and 0.125) | ✅ |
| Twist 2 (full P-may2026) | ✅ |
| Core paper figures | ✅ |
| DATE draft + camera-ready | ⏳ |

| Month | Planned | Actual |
|-------|---------|--------|
| May–Jun 2026 | Golden + RTL + D-sweep | ✅ |
| Jul 2026 | DMA + Hook A | ✅ |
| Jul–Aug 2026 | Energy + twists + figures | ✅ |
| Sep 2026 | DATE draft | ⏳ In progress (`paper/`) |

---

## License

RTL, Python, and docs are the project’s own work. Reproduction depends on third-party
**HDC-EMG** (Rahimi et al., GPLv3), fetched separately and not redistributed here.
