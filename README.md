# 1024-HDC — Streaming 1024-bit Hyperdimensional Computing on Zynq

A 1024-bit Hyperdimensional Computing (HDC) classifier in SystemVerilog for a
Xilinx Zynq-7020 (ZedBoard), built and **bit-exact verified** against a Python
golden reference, with EMG hand-gesture recognition under the frozen protocol
**P-may2026**.

The core executes the HDC primitives — **XOR bind**, **permute** (cyclic shift),
**majority bundle**, and **masked Hamming / popcount** associative-memory search —
on 1024-bit binary hypervectors (Binary Spatter Code model), reachable from the PS
over **AXI4-Lite** (control) and fed at inference rate over **AXI4-Stream + DMA**.

> **Target venue:** DATE 2027 (~Sep 2026 submission). The research contribution is
> a **three-axis accuracy/energy/area Pareto study** (dimension × bundle precision ×
> bit-pruning) plus **informed-vs-random pruning** and **cross-subject mask transfer**
> on real Zynq energy — not a re-port of prior FPGA-HDC accuracy.

---

## Status at a glance (June 2026)

| Area | State |
|------|-------|
| RTL datapath + 7 co-sim harnesses + `pruning_mask` | ✅ **Verified** (bit-exact vs Python) |
| D-sweep functional cosim (D ∈ {256, 512, 1024, 2048}) | ✅ **PASS** (200 cases/D) |
| D-sweep OOC synthesis (D ∈ {256, 512, 1024, 2048}) | ✅ **Complete** (see [`results/dsweep/`](results/dsweep/)) |
| Phase 1 — AXI-Lite bring-up | ✅ **Complete** (200/200 golden, ~3 µs/window) |
| Phase 2 — AXI-DMA stream bring-up | ✅ **Complete** (200/200 golden, ~7 µs/window) |
| Phase 3 — SG batch throughput | ✅ **Complete** (~216k windows/s, WNS +0.111 ns) |
| Phase 3 — full EMG replay on silicon | ✅ **PASS** (74.24%, 658k windows, Δ0.00% vs golden) |
| Phase 3 — energy (INA219) | ⏳ **Not started** |
| Hook A — Python Pareto sweep (D × CNT_W × pruning) | 🔄 **In progress** (~48 h full grid on VDI) |
| Twist 1 / Twist 2 (paper experiments) | ⏳ **Not started** |
| ARM-only + tiny-MLP baselines | ⏳ **Not started** |

Bring-up, verification, and the **D-axis characterisation** are **done**. The **Hook A
Python sweep** is running on VDI (~45–50 h); everything else below is **parallel or
downstream** — see [What's left](#whats-left).

---

## Results

All board numbers are **ZedBoard (xc7z020clg484-1) @ 100 MHz PL, Vivado 2024.2**.
Raw logs live under [`results/`](results/).

### RTL verification (co-simulation)

Every harness checks the RTL **bit-for-bit** against the Python golden reference.
Recorded on VDI 2026-06-25 (Vivado xsim; Questa `.do` harnesses equivalent).

| Harness | Cases | Proves | Log |
|---------|-------|--------|-----|
| `run_cosim.do` | 1000 | XOR bind + permute datapath | — |
| `run_bundle_cosim.do` | 500 | Majority bundler | — |
| `run_pruning_mask_cosim.do` | 64 | `pruning_mask.sv` (full + AXI word writes) | `results/xsim_pruning_mask.log` |
| `run_am_cosim.do` | 500 | Masked Hamming AM + argmin | `results/xsim_am.log` |
| `run_encoder_cosim.do` | 500 | Full EMG window encode | — |
| `run_core_cosim.do` | 500 | End-to-end encode → classify | `results/xsim_core.log` |
| `run_core_axi_cosim.do` | 200 | AXI4-Lite programming sequence | `results/xsim_core_axi.log` |
| `run_stream_cosim.do` | 200 | AXI4-Stream + back-pressure + random gaps | `results/xsim_stream.log` |
| `run_dsweep_cosim.do` | 200/D | Core at D ∈ {256, 512, 1024, 2048} | `results/xsim_dsweep_D*.log` |

### D-sweep — Hook A dimension axis (OOC synthesis + functional cosim)

Core-only out-of-context synthesis on **xc7z020clg484-1 @ 100 MHz** (Vivado 2024.2).
Full reports: [`results/dsweep/`](results/dsweep/).

| D | Slice LUT | Slice FF | LUT util | WNS (ns) | Fmax | Functional |
|---|-----------|----------|----------|----------|------|------------|
| 256 | 7,331 | 4,536 | 13.8% | 1.669 | 120 MHz | **PASS** |
| 512 | 14,422 | 8,935 | 27.1% | 1.452 | 117 MHz | **PASS** |
| 1024 | 28,600 | 17,784 | 53.8% | 0.781 | 109 MHz | **PASS** |
| 2048 | 59,261 | 35,424 | **111%** | 1.340 | 116 MHz | **PASS** |

LUT/FF scale ~linearly with D. **D=1024** is the timing tightest point (WNS 0.781 ns)
but still meets 100 MHz. **D=2048** exceeds OOC LUT budget on xc7z020 — a reportable
Pareto boundary for the full system (Phase 2 already at 66% LUT @ D=1024 + PS/DMA).

### Hook A — Python accuracy sweep (D × CNT_W × pruning)

RTL-matched `hdc_ref` encoder on the frozen **P-may2026** protocol (5 subjects, full
TEST split). Informed Fisher masks from pooled TRAIN windows; area proxy merged from
[`results/dsweep/`](results/dsweep/); energy on silicon deferred (INA219).

| Mode | Command | Status |
|------|---------|--------|
| Quick sanity | `python3 python_ref/run_hook_a_sweep.py --quick` | ✅ Done (~3 min, capped windows) |
| Full grid | `python3 python_ref/run_hook_a_sweep.py` | 🔄 **Running** (64 configs × 5 subjects) |

Outputs: [`results/hook_a/`](results/hook_a/) (`sweep_results.json`, `sweep_summary.csv`,
`sweep_results.partial.json` checkpoint while running). Config:
[`python_ref/config/hook_a_sweep.json`](python_ref/config/hook_a_sweep.json).

Full grid axes: **D** ∈ {256, 512, 1024, 2048} × **CNT_W** ∈ {3, 4, 5, 6} ×
**keep_ratio** ∈ {1.0, 0.5, 0.25, 0.125}. Expect **~45–50 h** wall time (single-core
Python encode). After completion: Pareto figure + 2–3 on-board anchor configs.

### Board bring-up — three measurement paths on the *same* core

| | Phase 1 — AXI-Lite | Phase 2 — DMA stream | Phase 3 — SG batch |
|--|--------------------|----------------------|--------------------|
| **Paper role** | Register-mapped baseline | Main inference path | Throughput + golden |
| **Golden** | 200/200 PASS | 200/200 PASS | 200/200 PASS (batch + per-window) |
| **Latency (mean)** | **3 µs**/window | **7 µs**/window | **58 µs** single · **~4 µs**/window batch |
| **Throughput** | ~333k win/s (micro) | ~143k win/s | **~216k win/s** (200-window SG batch) |
| **WNS @ 100 MHz** | +0.246 ns | +0.023 ns | **+0.111 ns** (post-route physopt) |
| **Logs** | `results/phase1/` | `results/phase2/` | `results/phase3/board_bench.txt` |

### Resource utilisation (post-route, xc7z020)

| | LUTs | FFs | Slices | BRAM | DSP |
|--|------|-----|--------|------|-----|
| Phase 1 (AXI-Lite) | 31,186 (58.6%) | 20,062 (18.9%) | ~88.5% | 0 | 0 |
| Phase 2/3 (DMA stream) | 35,206 (66.2%) | 27,639 (26.0%) | 12,810 (96.3%) | 0 | 0 |

**Zero DSP, zero BRAM** — pure-logic accelerator; `item_mem` inferred as LUT ROM.

### EMG full-dataset replay on silicon (Phase 3 v2)

| Metric | Value |
|--------|-------|
| Windows replayed (full TEST split, 5 subjects) | **658,004** |
| Correct | **488,550** |
| Board accuracy (RTL encoder) | **74.24%** |
| Python export-ref accuracy | **74.24%** |
| Board vs golden delta | **0.00%** → **PASS** (±0.5% gate) |

Evidence: [`results/phase3/board_emg_replay.txt`](results/phase3/board_emg_replay.txt).
The board reproduces its Python golden **exactly** over 658k real EMG windows — the
RTL + DMA inference path is proven correct on silicon.

---

## EMG accuracy: the two-baseline story (and how to defend 74%)

This project reports **two accuracy numbers on purpose**. They answer different
questions and must not be conflated.

| Track | Where | Encoding | Spatial accuracy | Role |
|-------|-------|----------|------------------|------|
| **Stage A — MAP parity** | Python | Bipolar MAP, D=10k | **90.36%** | Literal Rahimi parity (paper: 90.8%) |
| **Stage B — BSC reference** | Python | 4-channel records | **90.30% ± 0.13** | Frozen literature baseline @ D=1024 |
| **RTL encoder** | Python golden **+ ZedBoard** | Eq. (3.1) 4×5 grid, `encoder_top.sv` | **74.24%** | **Verified deployment path** |

Full write-up: [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md).

### Defending 74% against Rahimi et al. (ICRC 2016)

If asked *"Rahimi got ~90% — why is your hardware at 74%?"*, the answer has six parts:

1. **We *do* reproduce ~90% — and it's committed.** Stage A MAP hits **90.36%**
   (paper 90.8%) and Stage B BSC hits **90.30%** at D=1024, both in Python under the
   same protocol. The algorithm-level reproduction matches the literature. That box
   is ticked; it just lives in `python_ref/`, not on the FPGA.

2. **74% is a *different, hardware-faithful encoder* — not a worse classifier.**
   The silicon runs research-plan **Eq. (3.1)**: a 4×5 (channel × feature) grid with
   20 binds, position-permuted feature hypervectors, and seed-42 item-memory ROMs.
   Rahimi's ~90% comes from a **4-channel spatial-record** encoding (Stage B). These
   are two genuinely different HDC encodings, so identical accuracy was never expected.

3. **The number that matters is verification fidelity — and it is perfect.** The
   board matches its Python golden to **Δ0.00% over 658,004 windows**. That proves the
   RTL, DMA descriptor ring, and prototype loading are bit-exact correct. *Correctness
   of the deployed system is the deliverable, not beating a published accuracy.*

4. **My contribution is a systems/hardware study, not an accuracy contest.** Rahimi
   established *that* HDC classifies EMG. This work establishes *how efficiently a
   streaming 1024-bit HDC core runs on Zynq* — throughput (~216k win/s), latency
   (<50 µs), zero-DSP area, timing closure, and (next) an energy/accuracy Pareto.
   None of those depend on the absolute encoder accuracy.

5. **The headline claims are *relative*, so 74% vs 90% is irrelevant to them.**
   - Hook A: accuracy *retention* under pruning (≤2 pp drop at 50% prune) + energy cut.
   - Twist 1: informed pruning beats random by **≥5 pp at iso-density** — a within-run gap.
   - Twist 2: cross-subject mask transfer within **≤3 pp** of per-subject masks.
   All three are differences measured against the project's own 74.24% baseline.

6. **Reporting both numbers is a credibility *strength*.** The 74↔90 gap is fully
   traced (encoding topology, item-memory seed, feature handling) in
   `docs/Baseline_vs_RTL_Encoder.md`. A reviewer sees an honest, debugged pipeline —
   not a cherry-picked headline. (The earlier ~59% readings were a prototype-training
   bug, since fixed and documented.)

**One-liner:** *"We reproduced ~90% in Python (matching Rahimi); the FPGA runs a
different, bit-exact-verified encoder at 74.24%; the paper's contribution is measured
energy and informed-pruning Pareto on that verified path — not a second accuracy port."*

### Board pass criterion

EMG replay **PASS** = `|board_acc − export_ref| ≤ 0.5%`. The **90.30%** figure is a
Python reference only — **not** the silicon pass gate. The original plan target
(≥92% @ D=1024) was written for the Stage B encoding and is **retired** for the
silicon path (decision: June 2026, Option A).

---

## Repository layout

| Path | Contents |
|------|----------|
| `rtl/` | RTL: `xor_permute_top` (bind+permute), `permute_stage`, `bundle_unit`, `pruning_mask`, `popcount_am` (masked-Hamming AM), `item_mem`, `encoder_top` (EMG window encoder), `hdc_core_top` (encoder→AM), `hdc_core_axi_lite`, `hdc_stream_wrapper` (DMA stream). |
| `tb/` | Self-checking + co-sim testbenches (one per harness). |
| `sim/` | `run_*_cosim.do` one-command harnesses (gen vectors → compile → sim → PASS/FAIL). |
| `sw/` | Bare-metal: golden/bench (Phase 1), `hdc_dma_stream*` (Phase 2–3), `hdc_dma_stream_batch_bench`, `hdc_emg_board_test` (EMG replay). |
| `python_ref/` | Bit-exact golden model, EMG Stage A/B, Hook A sweep (`run_hook_a_sweep.py`), frozen baseline config. |
| `scripts/` | Golden prep, JTAG runners, EMG export/regen/pack, `ina219_log.py` (energy). |
| `board/HDC_DMA/` | ZedBoard Vitis workspace: platform, ELFs, JTAG run scripts. |
| `results/` | Per-phase board/synthesis logs (the source of every number above). |
| `docs/` | Research plan, `Baseline_vs_RTL_Encoder.md`, protocol/flow PDFs, end-to-end guide. |
| `vivado_pack/` | Vivado bring-up bundle. `1024HDC.mpf` | ModelSim project. |

> Third-party data/code (`python_ref/HDC-EMG/`, GPLv3) and generated co-sim vectors
> (`python_ref/vectors/`) are **not** committed (see `.gitignore`); both are reproducible.

---

## Quick start

### 1. RTL co-simulation (single source of truth)

```bash
vsim -c -do sim/run_cosim.do          # bind+permute (override count: NUM_CASES=…)
vsim -c -do sim/run_bundle_cosim.do   # bundler
vsim -c -do sim/run_pruning_mask_cosim.do  # pruning mask (full + AXI writes)
vsim -c -do sim/run_am_cosim.do       # associative memory
vsim -c -do sim/run_encoder_cosim.do  # EMG window encoder
vsim -c -do sim/run_core_cosim.do     # end-to-end core
vsim -c -do sim/run_core_axi_cosim.do # AXI4-Lite programming sequence
vsim -c -do sim/run_stream_cosim.do   # AXI4-Stream + back-pressure
vsim -c -do sim/run_dsweep_cosim.do   # functional D-sweep (256/512/1024/2048)
vivado -mode batch -source scripts/dsweep_synth.tcl   # OOC synth → results/dsweep/
```

Waveform/trace debug for the stream path: `vsim -c -do sim/run_stream_cosim_debug.do`
(`+DEBUG +TRACE=3 +WAVE` → `sim/waves/stream_cosim.vcd`).
Protocol/flow primers: `docs/AXI4_*_Protocol_Study.pdf`, `docs/HDC_*_Cosim_Flow.pdf`.

### 2. Python golden + EMG baselines

```bash
cd python_ref
pip install -r requirements.txt
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG   # one-time

python run_smoke_test.py                          # verify golden model
python run_emg_baseline.py                        # Stage B ~90% + cached RTL 74% summary
python run_emg_baseline.py --quick --no-parity    # fast (~7 s)
python run_emg_baseline.py --measure-rtl-ref --rtl-max-windows 5000  # re-measure RTL encoder
```

### 3. ZedBoard golden test (200 cases, seed 42)

```bash
bash scripts/prep_golden_test.sh        # → sw/golden_vectors.h  (Windows: prep_golden_test.ps1)
bash scripts/run_golden_jtag.sh         # JTAG → PASS: 200/200 golden cases
```

Base address `0x43C00000`. On ZedBoard the Digilent cable shares JTAG+UART; see
[`docs/USB_UART_JTAG.md`](docs/USB_UART_JTAG.md) for simultaneous serial + JTAG.
Prefer the JTAG result scripts if serial capture is unreliable during programming.
PL programming may need a retry or two.

### 4. Phase 2/3 — DMA stream, batch bench, EMG replay

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"   # Vivado project (for XSA/bitstream export)
cd board/HDC_DMA
bash build_sw.sh                 # golden + bench + batch + EMG ELFs (fast)

bash run_phase3_bench.sh         # batch throughput + golden → results/phase3/board_bench.txt
bash run_phase3_emg.sh           # full EMG replay        → results/phase3/board_emg_replay.txt
```

**Full EMG export** (one-time ~4 h) and the prototype-fix / DDR-split flow are
documented in [`results/phase3/README.md`](results/phase3/README.md).

---

## What's left

The decision (June 2026) is **Option A**: re-target Hook A against the **74.24% RTL
baseline**; absolute ≥92% is retired for silicon. **Bring-up, verification, and the
D-axis (synth + cosim) are complete.** Remaining work is measurement, the accuracy
Pareto, twist experiments, baselines, and the write-up.

### Tier 1 — finish Phase 3 infrastructure

- [ ] **Energy (INA219 + shunt on Vcc_int)** — wire per [`results/phase3/energy_setup.md`](results/phase3/energy_setup.md);
      log with [`scripts/ina219_log.py`](scripts/ina219_log.py); fill
      [`results/phase3/energy_batch.txt`](results/phase3/energy_batch.txt).
      *Blocks the real energy axis on every Pareto figure; can run in parallel with the Python sweep when the board is at the bench.*

### Tier 2 — close June RTL gaps (feed Hook A)

- [x] **D-sweep synthesis** (256 / 512 / 1024 / 2048) → LUT / WNS / f_max.
      [`results/dsweep/`](results/dsweep/) (2026-06-25).
- [x] **`pruning_mask.sv`** extracted + cosim harness (64 cases PASS).

### Tier 3 — research contributions (the paper)

- [ ] **Hook A — Python Pareto sweep** — D × CNT_W × pruning on `hdc_ref` / P-may2026.
      - [x] Sweep script + config shipped ([`python_ref/run_hook_a_sweep.py`](python_ref/run_hook_a_sweep.py),
            [`python_ref/config/hook_a_sweep.json`](python_ref/config/hook_a_sweep.json)).
      - [x] Quick sanity PASS ([`results/hook_a/`](results/hook_a/), `--quick`).
      - [ ] **Full grid running on VDI** — 64 configs × 5 subjects, ~45–50 h wall time;
            checkpoint: `results/hook_a/sweep_results.partial.json`.
      - [ ] **Final CSV/JSON + Pareto figure** — after full grid completes.
- [ ] **Hook A — on-board anchors (2–3 configs)** — replay EMG at Pareto knee points picked
      from the Python sweep (needs sweep ≥ D=1024 slice + board connected).
- [ ] **Twist 1** — informed vs random pruning at iso-density (target **≥5 pp** gap) — headline figure.
      *Can start now at one point (e.g. D=1024, keep=0.5) in parallel with the sweep.*
- [ ] **Twist 2** — cross-subject mask transfer (target **≤3 pp** vs per-subject masks).
      *Pilot possible on 5 subjects; full claim needs **36-subject export** (currently 5).*

### Tier 4 — comparison baselines

- [ ] **ARM-only HDC** (Cortex-A9, same algorithm in C/NEON) — for the **~10× energy** claim.
      *Board or cross-built bench; parallel with sweep.*
- [ ] **Tiny int8 MLP** (~5k params, 2 layers) — rebuttal baseline.
      *Pure Python train/eval; parallel with sweep.*
- [x] **AXI-Lite PL path** — Phase 1 register-mapped baseline (already done).

### Tier 5 — write-up

- [ ] **Paper figures** — Pareto (accuracy × energy proxy × LUT), Twist 1/2, Fisher heatmap.
- [ ] **DATE draft** (~Sep 2026) — fold in [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md).

### Parallel while the Hook A sweep runs

| Task | Resource | Blocks on sweep? |
|------|----------|------------------|
| INA219 energy batch | Board + I²C | No |
| Twist 1 @ one (D, keep) | ~2–4 h Python | No (avoid second full grid on same CPU) |
| Tiny int8 MLP baseline | Light Python | No |
| ARM-only HDC bench | Board / ARM build | No |
| Pareto plot script on `sweep_results.partial.json` | Minutes | No (preview only until full grid done) |
| On-board anchor pick + replay | Board | Yes — needs D=1024 rows in sweep output |
| Final Pareto table / paper numbers | — | Yes — needs full 64-cell grid |

### Plan vs actual (research plan §9.3)

| Month | Planned | Status |
|-------|---------|--------|
| May 2026 | Python golden + reproduce EMG number | ✅ Met (Stage A 90.36%, Stage B 90.30%) |
| Jun 2026 | Core RTL + co-sim; D verified | ✅ Met (`pruning_mask.sv`, D-sweep cosim + synth PASS) |
| Jul 2026 | Stream wrapper + DMA bring-up | ✅ Ahead (Phases 2–3, EMG replay PASS) |
| Aug 2026 | Hook A + Twist 1/2 + baselines + power | 🔄 Hook A Python sweep running; Twist/baselines/energy not started |
| Sep 2026 | Paper draft + DATE submit | ⏳ Not started |

---

## License / attribution

This repo's RTL, Python, and docs are the project's own work. The reproduction
depends on the third-party **HDC-EMG** dataset/code (Rahimi et al., GPLv3), fetched
separately and not redistributed here.
