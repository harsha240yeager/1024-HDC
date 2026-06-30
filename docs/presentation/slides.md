---
marp: true
size: 16:9
paginate: true
theme: hdc
style: |
  /* @theme hdc */
  section {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 22px;
    color: #1a2230;
    background: #ffffff;
    padding: 48px 56px;
  }
  h1 { color: #0a2540; font-size: 40px; margin-bottom: 6px; }
  h2 { color: #0a2540; font-size: 30px; border-bottom: 3px solid #2563eb; padding-bottom: 6px; margin-bottom: 14px; }
  h3 { color: #1d4ed8; font-size: 24px; margin: 8px 0 4px; }
  a { color: #2563eb; }
  strong { color: #0a2540; }
  code { background: #f1f5f9; color: #b91c1c; padding: 1px 6px; border-radius: 4px; font-size: 0.85em; }
  table { font-size: 18px; border-collapse: collapse; margin: 6px 0; }
  th { background: #0a2540; color: #fff; padding: 6px 10px; text-align: left; }
  td { border-bottom: 1px solid #e2e8f0; padding: 5px 10px; }
  tr:nth-child(even) td { background: #f8fafc; }
  section.lead { display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; background: linear-gradient(135deg, #0a2540 0%, #1d4ed8 100%); color: #fff; }
  section.lead h1 { color: #fff; font-size: 52px; }
  section.lead h2 { color: #cfe0ff; border: none; font-size: 26px; }
  section.lead p { color: #dbeafe; font-size: 20px; }
  .tag { background: #2563eb; color: #fff; font-size: 16px; font-weight: 600; padding: 3px 12px; border-radius: 12px; }
  .ok { color: #047857; font-weight: 700; }
  .warn { color: #b45309; font-weight: 700; }
  .no { color: #b91c1c; font-weight: 700; }
  .muted { color: #64748b; }
  .kpi { display: flex; gap: 16px; justify-content: center; margin-top: 18px; }
  .kpi .c { background: #0a2540; color: #fff; border-radius: 12px; padding: 16px 22px; text-align: center; }
  .kpi .c .v { font-size: 34px; font-weight: 800; }
  .kpi .c .l { font-size: 15px; opacity: .85; }
  .box { background: #eff6ff; border-left: 5px solid #2563eb; padding: 10px 16px; border-radius: 0 8px 8px 0; }
  .good { background: #ecfdf5; border-left: 5px solid #059669; padding: 10px 16px; border-radius: 0 8px 8px 0; }
  .danger { background: #fef2f2; border-left: 5px solid #dc2626; padding: 10px 16px; border-radius: 0 8px 8px 0; }
  footer { color: #94a3b8; font-size: 13px; }
  img[alt~="center"] { display: block; margin: 0 auto; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

# 1024-bit Hyperdimensional Computing Accelerator on Zynq-7020

## A streaming, bit-exact-verified HDC classifier for EMG hand-gesture recognition

Research progress review · Target venue: **DATE 2027**

Platform: Xilinx Zynq-7020 (ZedBoard) · SystemVerilog + Python golden reference

---

## The problem & motivation

- **Edge inference needs to be cheap and low-power** — wearables, prosthetics, IoT. Conventional CNN/MLP inference is multiply-heavy (needs DSP/GPU) and power-hungry.
- **Hyperdimensional Computing (HDC)** is a brain-inspired alternative: represent everything as long binary vectors and classify by *distance*. Operations are purely **bitwise** → ideal for FPGAs.
- **Application:** EMG hand-gesture recognition (same dataset as Rahimi et al., ICRC 2016), the standard HDC-on-EMG benchmark → enables direct comparison with literature.

<div class="box">

**Thesis:** A streaming 1024-bit HDC core on Zynq can classify EMG at high throughput with **zero DSP / zero BRAM**, and per-bit pruning can cut energy further with controlled accuracy loss. The contribution is a measured **accuracy / energy / area Pareto**, not a re-port of prior accuracy.

</div>

---

## What is Hyperdimensional Computing?

- Every concept (sensor value, feature, class) → one **1024-bit hypervector**.
- In high dimensions, random vectors are **near-orthogonal** → huge capacity + noise tolerance (flipping a few bits barely changes identity).
- Classification = **nearest prototype by Hamming distance** — no floating point, no matrix multiply.
- Model used: **Binary Spatter Code (BSC)** — binary vectors, XOR binding, Hamming similarity. The most hardware-friendly HDC flavour.

<div class="good">

**Why it suits FPGAs:** bitwise ops (XOR, shift, popcount) → cheap LUT logic, no multipliers. One-shot training (bundle examples once). Inherent error tolerance enables aggressive pruning / low voltage.

</div>

---

## The four HDC primitives

All of HDC is built from four operations — each is a verified RTL block here:

| Primitive | Math | Meaning | RTL block |
|-----------|------|---------|-----------|
| **Bind** | XOR (A ⊕ B) | Associate two concepts | `xor_permute_top` |
| **Permute** | cyclic shift ρ(A) | Encode position / order | `permute_stage` |
| **Bundle** | majority vote | Superpose into a "set" vector | `bundle_unit` |
| **Search** | argmin Hamming | Classify (nearest prototype) | `popcount_am` |

<div class="box">

Encoding = **bind + permute + bundle** → builds the query hypervector. **Search** classifies it. Everything is XOR, shift, and popcount — no DSP.

</div>

---

## Application — EMG hand-gesture recognition

**Task:** recognise hand gestures from 4-channel forearm EMG signals → gesture-controlled prosthetics.

How an EMG window becomes a class:

1. Capture a short **window** of the 4 EMG channels.
2. Quantise per-channel features into **16 discrete levels**.
3. Look up each (channel, feature, value) in **item-memory** hypervector ROMs.
4. **Bind + permute + bundle** → one 1024-bit **query hypervector**.
5. **Masked Hamming** search vs the **5 class prototypes** → nearest wins.

<div class="box">

**"Training" in HDC = bundling.** No gradient descent — just superpose all of a gesture's training windows into one prototype. Inference is a single nearest-neighbour search.

</div>

---

## System architecture — Zynq PS + PL

![center w:1000](diagrams/arch.svg)

**PS** (ARM) streams EMG windows from DDR over **AXI-DMA**; the **PL** HDC core encodes + classifies and returns labels. Control via **AXI4-Lite**, data via **AXI4-Stream**.

---

## The encoding datapath

![center w:1080](diagrams/pipeline.svg)

Research-plan **Eq. (3.1)**: a 4 channel × 5 feature grid (20 binds), position-permuted, bundled into the query HV. The new **`pruning_mask`** gates which bits count in the associative-memory distance.

---

## Module hierarchy

![center h:430](diagrams/hierarchy.svg)

<div class="good">

**New: `pruning_mask.sv` extracted as a dedicated module** (research-plan §5.3.3) — holds the D-bit mask and gates the Hamming distance, cutting dynamic energy ∝ prune ratio. Verified bit-exact (**129/129 checks PASS**).

</div>

---

## Computational microarchitecture — word-serial datapath

![center w:1080](diagrams/compute_datapath.svg)

The 1024-bit HV is stored as **16 × 64-bit words**. The associative memory streams **one 64-bit word per cycle**: `XOR` query⊕prototype → `AND` mask word → **64-bit popcount** (LUT adder tree) → accumulate distance `d_k`. Loop 16 words per class, 8 classes, then `argmin`.

<div class="good">

**Why word-serial?** A full 1024-bit popcount tree is large and timing-critical. Processing 64 bits/cycle reuses **one small popcount + one accumulator** → **0 DSP, 0 BRAM**, easy 100 MHz timing. The `pruning_mask` word simply zeros gated bits *before* popcount, so pruning directly removes switching activity.

</div>

---

## Cycle-level behaviour — AM FSM & latency

![center w:760](diagrams/compute_fsm.svg)

| Stage | RTL block | Cycles | Notes |
|-------|-----------|--------|-------|
| Encode (bind+permute+bundle) | `encoder_top` | ~N_PAIRS + 3 = **~23** | 1 (channel,feature) pair/cycle, 4×5 grid |
| Bundle majority | `bundle_unit` | combinational | 1024 saturating counters, width **CNT_W=6** |
| Classify (masked Hamming) | `popcount_am` | N_CLASS·(2·WORDS+1) = **264** | 8 classes × (16 words × 2 + compare) |
| **Per-window total** | core | **≈ 287 cycles** | ≈ 2.9 µs @ 100 MHz; pipelined across windows |

<div class="box">

`CNT_W` (bundle counter width) and the **prune ratio** are the two micro-architectural knobs of Hook A — both change the datapath's switching/area without touching its structure.

</div>

---

## Verification — the Python golden reference

![center w:980](diagrams/verification.svg)

A **bit-exact Python model** (`hdc_ref.py`) is the single source of truth — it generates both stimulus *and* expected output, so RTL and reference cannot silently drift.

---

## Verification coverage — 7 + 1 harnesses, all bit-exact

| Co-sim harness | Cases | Proves |
|----------------|-------|--------|
| `run_cosim` | 1000 | XOR bind + permute datapath |
| `run_bundle_cosim` | 500 | Majority bundler |
| `run_am_cosim` | 500 | Masked Hamming AM + argmin |
| `run_encoder_cosim` | 500 | Full EMG window encode |
| `run_core_cosim` | 500 | End-to-end encode → classify |
| `run_core_axi_cosim` | 200 | AXI4-Lite programming sequence |
| `run_stream_cosim` | 200 | AXI4-Stream + back-pressure |
| `run_pruning_mask_cosim` | 64 | New pruning-mask module |

<span class="ok">All PASS</span> on both Questa and Vivado xsim (June 2026).

---

## Board results — three measurement paths, same core

<div class="kpi">
<div class="c"><div class="v">74.24%</div><div class="l">Board EMG accuracy</div></div>
<div class="c"><div class="v">Δ 0.00%</div><div class="l">Board vs golden (658k win)</div></div>
<div class="c"><div class="v">~216k</div><div class="l">windows / second</div></div>
<div class="c"><div class="v">0 / 0</div><div class="l">DSP / BRAM</div></div>
</div>

| | Phase 1 — AXI-Lite | Phase 2 — DMA stream | Phase 3 — SG batch |
|--|--------------------|----------------------|--------------------|
| Golden test | <span class="ok">200/200</span> | <span class="ok">200/200</span> | <span class="ok">200/200</span> |
| Mean latency | 3 µs/win | 7 µs/win | ~4 µs/win (batch) |
| Throughput | ~333k/s (micro) | ~143k/s | **~216k/s** |
| WNS @ 100 MHz | +0.246 ns | +0.023 ns | **+0.111 ns** |

---

## Resource utilisation & the D-sweep <span class="tag">June gap CLOSED</span>

**Integrated (PS + DMA + core), post-route xc7z020:** 35,206 LUT (66.2%), 96.3% slices, **0 DSP, 0 BRAM**.

**OOC core-only D-sweep** (functional cosim PASS + synthesis, all D):

| D | Slice LUT | LUT util | WNS (ns) | Fmax (MHz) | Cosim |
|---|-----------|----------|----------|------------|-------|
| 256 | 7,331 | 13.8% | 1.669 | 120.0 | <span class="ok">PASS</span> |
| 512 | 14,422 | 27.1% | 1.452 | 117.0 | <span class="ok">PASS</span> |
| 1024 | 28,600 | 53.8% | 0.781 | 108.5 | <span class="ok">PASS</span> |
| 2048 | 59,261 | **111.4%** | 1.340 | 115.5 | <span class="ok">PASS</span> |

<span class="muted">LUT scales ~linearly with D. **D=2048 exceeds device LUT budget → a reportable Pareto boundary.**</span>

---

## EMG accuracy — the two-baseline story <span class="tag">read carefully</span>

We report **two numbers on purpose** — they answer different questions.

| Track | Where | Encoding | Accuracy | Role |
|-------|-------|----------|----------|------|
| Stage A — MAP | Python | Bipolar MAP, D=10k | <span class="ok">90.36%</span> | Literal Rahimi parity (paper 90.8%) |
| Stage B — BSC | Python | 4-ch spatial records | <span class="ok">90.30%</span> | Frozen literature baseline |
| **RTL encoder** | Python **+ board** | Eq. (3.1) 4×5 grid | <span class="warn">74.24%</span> | **Verified deployment path** |

<div class="danger">

**Defense one-liner:** *"We reproduced ~90% in Python (matching Rahimi). The FPGA runs a different, bit-exact-verified encoder at 74.24%. The contribution is measured energy + informed-pruning Pareto on that verified path — not a second accuracy port."*

</div>

---

## Why 74% is not a weakness — six points

1. **We do reproduce ~90%** — Stage A 90.36% / Stage B 90.30%, committed in Python.
2. **74% is a *different* encoder**, not a worse one — Eq. (3.1) hardware grid vs Rahimi's spatial records.
3. **Verification fidelity is perfect** — board = golden to **Δ0.00% over 658,004 windows**.
4. **The contribution is a systems study** — throughput, latency, zero-DSP area, energy Pareto.
5. **Headline claims are *relative*** — pruning retention, informed-vs-random gap, transfer — 74 vs 90 is irrelevant to them.
6. **Reporting both is a credibility strength** — gap fully traced; honest, debugged pipeline.

---

## Research novelty — Hook A: 3-axis Pareto <span class="tag">contribution</span>

Prior FPGA-HDC prunes **dimension**. The under-explored axis is **which bits** to keep.

| Axis | Values | Mechanism | Status |
|------|--------|-----------|--------|
| Dimension **D** | 256 / 512 / 1024 / 2048 | parameterised RTL | <span class="ok">DONE (synth+cosim)</span> |
| Bundle precision **CNT_W** | 3 / 4 / 5 / 6 | majority-vote resolution | <span class="warn">running (Python sweep)</span> |
| **Bit-pruning ratio** | 0 / 50 / 75 / 87.5% | Fisher mask via `pruning_mask` | <span class="warn">running (Python sweep)</span> |

<div class="box">

Map the **accuracy / energy / area** trade-off surface for HDC-on-FPGA. D-axis measured on silicon; the **64-cell `run_hook_a_sweep.py` grid** (D × CNT_W × prune) is running (quick-sanity PASS) — feeds accuracy; **INA219** adds the real energy axis.

</div>

---

## Research novelty — Twist 1 & Twist 2

### Twist 1 — informed vs random pruning (headline result)
At each prune ratio, compare a **Fisher-ratio mask** (keep most discriminative bits) vs a **random mask of identical density**.
**Claim:** informed beats random by **≥5 pp at iso-density** → *bit position matters, not just bit count.*

### Twist 2 — cross-subject mask transferability
Train the mask on some EMG subjects, deploy unchanged on held-out subjects.
**Either outcome publishable:** transfers (≤3 pp) → universal "bit-importance map"; fails → motivates on-device adaptation. <span class="muted">(needs 36-subject export; currently 5)</span>

---

## Comparison baselines — why HDC-on-PL <span class="tag">accuracy done</span>

Same **P-may2026** protocol (5 subjects, full TEST). Accuracy complete; energy pending INA219.

| Baseline | Accuracy | Latency / window | Status |
|----------|----------|------------------|--------|
| **PL DMA (this work)** | 74.24% (board) | **~4 µs** (batch) | <span class="ok">Phase 3 PASS</span> |
| **ARM-only HDC** (C, Cortex-A9) | 74.15% | **818 µs** (1,222 win/s) | <span class="ok">200/200 golden</span> |
| **Tiny int8 MLP** (~5.8k params) | 93.01% fp / 92.99% int8 | — | <span class="ok">full 5 subjects</span> |
| AXI-Lite PL path | — | ~3 µs | <span class="ok">Phase 1</span> |

<div class="good">

**PL DMA is ~200× faster per window than ARM software** (4 µs vs 818 µs) at matched accuracy (74.24 vs 74.15%). The MLP shows a higher-accuracy NN reference; INA219 will add the **energy** column for the ~10× efficiency claim.

</div>

---

## Status & roadmap

![center w:1080](diagrams/roadmap.svg)

Bring-up, all **June** RTL deliverables, **and the comparison baselines** are **complete and ahead of schedule**. Remaining: INA219 energy → finish Hook A sweep → twists → the paper.

---

## Summary & next steps

**Done & verified (on GitHub):**
- <span class="ok">RTL datapath + 8 co-sim harnesses, bit-exact</span>
- <span class="ok">Phases 1–3 board bring-up; EMG replay 74.24%, Δ0.00% over 658k windows</span>
- <span class="ok">`pruning_mask.sv` extracted; D-sweep synth + cosim (256–2048)</span>
- <span class="ok">Python ~90% baselines reproduced</span>
- <span class="ok">Comparison baselines: ARM HDC (74.15%, 818 µs/win) + tiny int8 MLP (93.0%)</span>

**Next (critical path):**
1. <span class="warn">INA219 energy measurement</span> (unblocks all Pareto/energy + ARM-vs-PL ~10× claim)
2. Hook A — `run_hook_a_sweep.py` grid (D × CNT_W × prune) running → board anchors
3. Twist 1 (informed vs random) — headline figure · Twist 2 (cross-subject)
4. Paper figures + DATE 2027 draft

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Thank you

## Questions & discussion

The hardware is **done and provably correct** (bit-exact on 658k windows).
74% is a faithful hardware encoder — we already match ~90% in Python.
The **research** is the energy/accuracy Pareto + informed-pruning result.
