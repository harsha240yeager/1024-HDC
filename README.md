# 1024-HDC — Streaming Hyperdimensional Computing on Zynq

A 1024-bit Hyperdimensional Computing (HDC) classifier in SystemVerilog for the
Xilinx Zynq-7020 (ZedBoard), **bit-exact verified** against a Python golden
reference and validated on silicon with EMG hand-gesture recognition under the
frozen protocol **P-may2026**.

The core implements the HDC primitives — **XOR bind**, **permute** (cyclic shift),
**majority bundle**, and **masked Hamming / popcount** associative-memory search —
on 1024-bit binary hypervectors (Binary Spatter Code model). It is controlled from
the PS over **AXI4-Lite** and fed at inference rate over **AXI4-Stream + DMA**.

> **Target venue:** DATE 2027 (~Sep 2026 submission).
> **Contribution:** a three-axis accuracy / energy / area Pareto study
> (dimension × bundle precision × bit-pruning), plus informed-vs-random pruning
> and cross-subject mask transfer on real Zynq energy — *not* a re-port of prior
> FPGA-HDC accuracy.

**Platform:** ZedBoard `xc7z020clg484-1` @ 100 MHz PL · Vivado 2024.2 · ModelSim/Questa
**Repo:** `harsha240yeager/1024-HDC`

---

## Contents

- [Status](#status)
- [Results](#results)
- [Accuracy: the two-baseline story](#accuracy-the-two-baseline-story)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Roadmap](#roadmap)
- [License](#license)

---

## Status

*Last updated: July 2026.*

**Done:** RTL + verification + Zynq bring-up (Phases 1–3) + **`pruning_mask.sv`**
(cosim PASS) + **D-sweep** (functional cosim + OOC synth) + Tier 4 baselines (ARM HDC + MLP)
+ **Hook A full Python sweep** (64 configs × 5 subjects, **320 rows**, ~44 h, 2026-07-01).
**Next:** Pareto figure, INA219 energy, on-board anchor replays (A/B/C below), Twist 1/2, write-up.

| Area | State |
|------|-------|
| RTL datapath + 7 co-sim harnesses + `pruning_mask` | ✅ Verified (bit-exact vs Python) |
| D-sweep functional cosim — D ∈ {256, 512, 1024, 2048} | ✅ PASS (200 cases/D) |
| D-sweep OOC synthesis — D ∈ {256, 512, 1024, 2048} | ✅ Complete ([`results/dsweep/`](results/dsweep/)) |
| Phase 1 — AXI-Lite bring-up | ✅ 200/200 golden, ~3 µs/window |
| Phase 2 — AXI-DMA stream bring-up | ✅ 200/200 golden, ~7 µs/window |
| Phase 3 — SG batch throughput | ✅ ~216k windows/s, WNS +0.111 ns |
| Phase 3 — full EMG replay on silicon | ✅ PASS — 74.24%, 658k windows, Δ0.00% vs golden |
| ARM HDC baseline (C) | ✅ 74.15% accuracy · 819 µs/window on-board (200/200 golden) |
| Tiny int8 MLP baseline | ✅ 93.01% float / 92.99% int8 (5 subjects, full TEST) |
| Hook A — Python Pareto sweep (D × CNT_W × pruning) | ✅ Complete (~44 h; [`results/hook_a/`](results/hook_a/)) |
| Phase 3 — energy (INA219) | ⏳ Tooling ready; measurement pending |
| Twist 1 · Twist 2 (paper experiments) | ⏳ Not started |

---

## Results

All board numbers are from ZedBoard `xc7z020clg484-1` @ 100 MHz PL (Vivado 2024.2).
Raw logs live under [`results/`](results/).

### RTL verification (co-simulation)

Each harness checks the RTL **bit-for-bit** against the Python golden reference
(recorded on VDI 2026-06-25; Vivado xsim, Questa `.do` harnesses equivalent).

| Harness | Cases | Proves |
|---------|-------|--------|
| `run_cosim.do` | 1000 | XOR bind + permute datapath |
| `run_bundle_cosim.do` | 500 | Majority bundler |
| `run_pruning_mask_cosim.do` | 64 | `pruning_mask.sv` (full + AXI word writes) |
| `run_am_cosim.do` | 500 | Masked Hamming AM + argmin |
| `run_encoder_cosim.do` | 500 | Full EMG window encode |
| `run_core_cosim.do` | 500 | End-to-end encode → classify |
| `run_core_axi_cosim.do` | 200 | AXI4-Lite programming sequence |
| `run_stream_cosim.do` | 200 | AXI4-Stream + back-pressure + random gaps |
| `run_dsweep_cosim.do` | 200/D | Core at D ∈ {256, 512, 1024, 2048} |

### D-sweep — Hook A dimension axis

Core-only out-of-context synthesis (Vivado 2024.2). Full reports in [`results/dsweep/`](results/dsweep/).

| D | Slice LUT | Slice FF | LUT util | WNS (ns) | Fmax | Functional |
|---|-----------|----------|----------|----------|------|------------|
| 256 | 7,331 | 4,536 | 13.8% | 1.669 | 120 MHz | PASS |
| 512 | 14,422 | 8,935 | 27.1% | 1.452 | 117 MHz | PASS |
| 1024 | 28,600 | 17,784 | 53.8% | 0.781 | 109 MHz | PASS |
| 2048 | 59,261 | 35,424 | 111% | 1.340 | 116 MHz | PASS |

LUT/FF scale ~linearly with D. **D=1024** is the timing-tightest point (WNS 0.781 ns)
but still meets 100 MHz. **D=2048** exceeds the OOC LUT budget on xc7z020 — a
reportable Pareto boundary.

### Hook A — Python accuracy sweep (D × CNT_W × pruning)

RTL-matched `hdc_ref` encoder on the frozen **P-may2026** protocol (5 subjects, full
TEST split). Informed Fisher masks from pooled TRAIN windows; area proxy merged from
[`results/dsweep/`](results/dsweep/); on-silicon energy deferred (INA219).

| Mode | Command | Status |
|------|---------|--------|
| Quick sanity | `python3 python_ref/run_hook_a_sweep.py --quick` | ✅ Done (~3 min, capped windows) |
| Full grid | `python3 python_ref/run_hook_a_sweep.py` | ✅ Done (320 rows, ~44 h, 2026-07-01) |

Grid: **D** ∈ {256, 512, 1024, 2048} × **CNT_W** ∈ {3, 4, 5, 6} ×
**keep_ratio** ∈ {1.0, 0.5, 0.25, 0.125}.
Outputs: [`results/hook_a/`](results/hook_a/) (`sweep_results.json`, `sweep_summary.csv`).
Config: [`python_ref/config/hook_a_sweep.json`](python_ref/config/hook_a_sweep.json).

**Headline (5 subjects, informed Fisher mask):**

| Reference | Spatial mean |
|-----------|--------------|
| **D=1024, CNT_W=6, keep=1.0** (Python / matches silicon) | **74.15%** |
| Board RTL EMG replay | **74.24%** |
| Best grid point (D=2048, CNT_W≥4) | **77.62%** (59261 LUT — OOC only, > device) |
| CNT_W=3 (all D) | **59.48%** (bundle-precision floor) |

At **D=1024, CNT_W≥4**, accuracy is **flat at 74.15%** from 0% → **87.5%** pruning
(energy proxy `(D/1024)×keep_ratio` scales down; replace with INA219 at board anchors).

**On-board anchor picks** (D=1024 bitstream — reprogram pruning mask before each EMG replay):

| Anchor | CNT_W | keep | Prune | Python acc | Role |
|--------|-------|------|-------|------------|------|
| **A — baseline** | 6 | 1.0 | 0% | 74.15% | Must match prior 74.24% board replay |
| **B — knee** | 6 | 0.5 | 50% | 74.15% | Same accuracy, half energy proxy |
| **C — aggressive** | 6 | 0.125 | 87.5% | 74.15% | Max prune, zero acc drop (informed mask) |

Full Pareto table + area ladder: [`results/hook_a/README.md`](results/hook_a/README.md).

### Tier 4 — comparison baselines

Same **P-may2026** protocol as board replay. Details in [`results/baselines/`](results/baselines/).

| Baseline | Accuracy (spatial mean) | On-board latency | Status |
|----------|-------------------------|------------------|--------|
| Board RTL encoder (reference) | **74.24%** | ~4 µs/window (batch) | ✅ Phase 3 EMG replay PASS |
| ARM HDC (`sw/hdc_arm_ref.c`) | 74.15% | **819 µs**/window (mean) | ✅ Host + board 200/200 golden |
| Tiny int8 MLP (~5.8k params) | 93.01% float / 92.99% int8 | — | ✅ Full 5 subjects, 25 epochs |
| AXI-Lite PL path | — | ~3 µs/window | ✅ Phase 1 latency baseline |

PL DMA batch is **~200×** faster per window than ARM software (819 µs vs ~4 µs).
*Pending:* INA219 energy on both paths for the ~10× energy claim.
Runners: [`python_ref/run_arm_hdc_baseline.py`](python_ref/run_arm_hdc_baseline.py),
[`python_ref/run_mlp_baseline.py`](python_ref/run_mlp_baseline.py),
[`python_ref/run_baselines.py`](python_ref/run_baselines.py).
Build C lib: `bash scripts/build_hdc_arm_host.sh shared`.
On-board ARM timing: `bash board/HDC_DMA/run_arm_bench.sh`.

### Board bring-up — three measurement paths on the same core

| | Phase 1 — AXI-Lite | Phase 2 — DMA stream | Phase 3 — SG batch |
|--|--------------------|----------------------|--------------------|
| Paper role | Register-mapped baseline | Main inference path | Throughput + golden |
| Golden | 200/200 PASS | 200/200 PASS | 200/200 PASS (batch + per-window) |
| Latency (mean) | 3 µs/window | 7 µs/window | 58 µs single · ~4 µs/window batch |
| Throughput | ~333k win/s (micro) | ~143k win/s | ~216k win/s (200-window SG batch) |
| WNS @ 100 MHz | +0.246 ns | +0.023 ns | +0.111 ns (post-route physopt) |
| Logs | `results/phase1/` | `results/phase2/` | `results/phase3/board_bench.txt` |

### Resource utilisation (post-route, xc7z020)

| | LUTs | FFs | Slices | BRAM | DSP |
|--|------|-----|--------|------|-----|
| Phase 1 (AXI-Lite) | 31,186 (58.6%) | 20,062 (18.9%) | ~88.5% | 0 | 0 |
| Phase 2/3 (DMA stream) | 35,206 (66.2%) | 27,639 (26.0%) | 12,810 (96.3%) | 0 | 0 |

**Zero DSP, zero BRAM** — pure-logic accelerator; `item_mem` inferred as LUT ROM.

### EMG full-dataset replay on silicon (Phase 3 v2)

| Metric | Value |
|--------|-------|
| Windows replayed (full TEST split, 5 subjects) | 658,004 |
| Correct | 488,550 |
| Board accuracy (RTL encoder) | **74.24%** |
| Python export-ref accuracy | 74.24% |
| Board vs golden delta | **0.00%** → PASS (±0.5% gate) |

Evidence: [`results/phase3/board_emg_replay.txt`](results/phase3/board_emg_replay.txt).
The board reproduces its Python golden **exactly** over 658k real EMG windows.

---

## Accuracy: the two-baseline story

This project reports **two accuracy numbers on purpose** — they answer different
questions and must not be conflated.

| Track | Where | Encoding | Accuracy | Role |
|-------|-------|----------|----------|------|
| Stage A — MAP parity | Python | Bipolar MAP, D=10k | 90.36% | Literature parity (Rahimi ~90.8%) |
| Stage B — BSC reference | Python | 4-channel records | 90.30% ± 0.13 | Frozen literature baseline @ D=1024 |
| RTL encoder | Python golden **+ ZedBoard** | Eq. (3.1) 4×5 grid | **74.24%** | **Verified deployment path** |

**Why 74% on hardware is not a weakness:** the silicon runs a *different,
hardware-faithful encoder* (Eq. 3.1 grid, seed-42 item memory), not Rahimi's
4-channel spatial-record encoding — so identical accuracy was never expected. The
~90% literature result *is* reproduced in Python (`python_ref/`). The deliverable is
**verification fidelity** (board matches golden to Δ0.00% over 658k windows) and a
**systems study** (throughput, latency, zero-DSP area, energy/pruning Pareto). All
headline claims are **relative** to this 74.24% baseline, so the 74↔90 gap does not
affect them.

Full rationale and pass criteria: [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md).
EMG replay PASS gate is `|board_acc − export_ref| ≤ 0.5%` — the 90.30% figure is a
Python reference only, not the silicon gate. The original ≥92% target (Stage B
encoding) is retired for the silicon path (June 2026, Option A).

---

## Repository layout

| Path | Contents |
|------|----------|
| `rtl/` | `xor_permute_top`, `permute_stage`, `bundle_unit`, `pruning_mask`, `popcount_am`, `item_mem`, `encoder_top`, `hdc_core_top`, `hdc_core_axi_lite`, `hdc_stream_wrapper` |
| `tb/` | Self-checking + co-sim testbenches (one per harness) |
| `sim/` | `run_*_cosim.do` one-command harnesses (gen vectors → compile → sim → PASS/FAIL) |
| `sw/` | Bare-metal drivers + `hdc_arm_ref.c` / `hdc_arm_bench.c` (ARM HDC baseline + on-board timing) |
| `python_ref/` | Golden model, EMG baselines, Hook A sweep, Tier 4 runners (`run_*_baseline.py`) |
| `scripts/` | Golden prep, JTAG runners, EMG export, `build_hdc_arm_host.sh`, energy tooling (`ina219_log.py`) |
| `board/HDC_DMA/` | ZedBoard Vitis workspace: platform, ELFs, JTAG run scripts |
| `results/` | Per-phase board / synthesis logs + [`hook_a/`](results/hook_a/) sweep + [`baselines/`](results/baselines/) |
| `docs/` | Research plan, `Baseline_vs_RTL_Encoder.md`, protocol/flow PDFs, end-to-end guide |
| `vivado_pack/` | Vivado bring-up bundle |

> Third-party data/code (`python_ref/HDC-EMG/`, GPLv3) and generated co-sim vectors
> (`python_ref/vectors/`) are **not** committed (see `.gitignore`); both are reproducible.

---

## Quick start

### 1 · RTL co-simulation (single source of truth)

```bash
vsim -c -do sim/run_cosim.do               # bind + permute
vsim -c -do sim/run_bundle_cosim.do        # bundler
vsim -c -do sim/run_pruning_mask_cosim.do  # pruning mask (full + AXI writes)
vsim -c -do sim/run_am_cosim.do            # associative memory
vsim -c -do sim/run_encoder_cosim.do       # EMG window encoder
vsim -c -do sim/run_core_cosim.do          # end-to-end core
vsim -c -do sim/run_core_axi_cosim.do      # AXI4-Lite programming sequence
vsim -c -do sim/run_stream_cosim.do        # AXI4-Stream + back-pressure
vsim -c -do sim/run_dsweep_cosim.do        # functional D-sweep (256/512/1024/2048)
vivado -mode batch -source scripts/dsweep_synth.tcl   # OOC synth → results/dsweep/
```

Stream-path waveform debug: `vsim -c -do sim/run_stream_cosim_debug.do`
(`+DEBUG +TRACE=3 +WAVE` → `sim/waves/stream_cosim.vcd`).

### 2 · Python golden, EMG baselines, Hook A

```bash
cd python_ref
pip install -r requirements.txt
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG   # one-time

python run_smoke_test.py                              # verify golden model
python run_emg_baseline.py                            # Stage B ~90% + cached RTL 74%
python run_emg_baseline.py --quick --no-parity        # fast (~7 s)

python run_hook_a_sweep.py --quick                    # Hook A sanity (~3 min)
python run_hook_a_sweep.py                             # full grid (~44 h) → results/hook_a/
```

Full sweep results (2026-07-01): [`results/hook_a/sweep_summary.csv`](results/hook_a/sweep_summary.csv).

### 3 · Tier 4 baselines (ARM HDC + MLP)

```bash
bash scripts/build_hdc_arm_host.sh shared     # once: build libhdc_arm_ref.so
python3 python_ref/run_arm_hdc_baseline.py    # ARM HDC accuracy (~2 min, full split)
python3 python_ref/run_mlp_baseline.py        # tiny int8 MLP (~minutes)
python3 python_ref/run_baselines.py           # both → results/baselines/

bash board/HDC_DMA/run_arm_bench.sh           # on-board ARM software timing (ZedBoard + JTAG)
```

### 4 · ZedBoard golden test (200 cases, seed 42)

```bash
bash scripts/prep_golden_test.sh    # → sw/golden_vectors.h  (Windows: prep_golden_test.ps1)
bash scripts/run_golden_jtag.sh     # JTAG → PASS: 200/200 golden cases
```

Base address `0x43C00000`. The Digilent cable shares JTAG+UART; see
[`docs/USB_UART_JTAG.md`](docs/USB_UART_JTAG.md) for simultaneous serial + JTAG.
Prefer the JTAG result scripts if serial capture is unreliable; PL programming may
need a retry or two.

### 5 · Phase 2/3 — DMA stream, batch bench, EMG replay

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"   # Vivado project (XSA/bitstream export)
cd board/HDC_DMA
bash build_sw.sh                 # golden + bench + batch + EMG ELFs

bash run_phase3_bench.sh         # batch throughput + golden → results/phase3/board_bench.txt
bash run_phase3_emg.sh           # full EMG replay          → results/phase3/board_emg_replay.txt
```

Full EMG export (one-time ~4 h) and the prototype-fix / DDR-split flow are documented
in [`results/phase3/README.md`](results/phase3/README.md).

---

## Roadmap

Hook A is re-targeted (June 2026, Option A) against the **74.24% RTL baseline**;
the absolute ≥92% target is retired for the silicon path.

**Done:** bring-up, verification, **`pruning_mask.sv`**, **D-sweep**, Tier 4 baselines,
and **Hook A full Python sweep** (320 rows, 64 configs, 2026-07-01).
**Remaining:** Pareto figure, INA219 energy, on-board anchor replays, Twist 1/2, DATE write-up.

**Tier 1 — finish Phase 3 infrastructure**
- [ ] Energy (INA219 + shunt) — wire per [`results/phase3/energy_setup.md`](results/phase3/energy_setup.md), log with [`scripts/ina219_log.py`](scripts/ina219_log.py), fill [`results/phase3/energy_batch.txt`](results/phase3/energy_batch.txt). *Blocks Pareto energy axis and ARM-vs-PL ~10× claim.*

**Tier 3 — research contributions**
- [x] Hook A Python sweep — 320 rows, 64 configs, ~44 h ([`results/hook_a/`](results/hook_a/))
- [ ] Hook A Pareto figure — accuracy × LUT × energy_proxy; overlay INA219 at anchors A/B/C
- [ ] Hook A on-board anchors @ D=1024:

  | Anchor | keep | Prune | Python acc |
  |--------|------|-------|------------|
  | A — baseline | 1.0 | 0% | 74.15% |
  | B — knee | 0.5 | 50% | 74.15% |
  | C — aggressive | 0.125 | 87.5% | 74.15% |

- [ ] Twist 1 — informed vs random pruning at iso-density (target ≥5 pp) @ D=1024, keep=0.5
- [ ] Twist 2 — cross-subject mask transfer (target ≤3 pp); pilot on 5 subjects

**Tier 4 — comparison baselines (accuracy complete)**
- [x] ARM HDC accuracy — 74.15% spatial mean (host C verify)
- [x] ARM HDC on-board timing — 819 µs/window, 200/200 golden on Cortex-A9
- [x] Tiny int8 MLP — 93.01% float / 92.99% int8, full 5 subjects
- [x] AXI-Lite PL path — Phase 1 baseline
- [ ] ARM vs PL energy (INA219) — ties to Tier 1

**Tier 5 — write-up**
- [ ] Paper figures — Pareto (accuracy × energy × LUT), Twist 1/2, Fisher heatmap, baseline table
- [ ] DATE draft (~Sep 2026) — fold in [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md)

### Next steps (post-sweep)

| Task | Resource | Priority |
|------|----------|----------|
| INA219 energy (PL batch + ARM path) | Board + I²C | **High** |
| On-board anchor replay (A/B/C) | Board | High |
| Pareto figure from `sweep_summary.csv` | Python/matplotlib | High |
| Twist 1 @ D=1024, keep=0.5 | ~2–4 h Python | Medium |
| Twist 2 pilot (5 subjects) | Python | Medium |
| DATE draft | — | Sep 2026 |

### Plan vs actual (research plan §9.3)

| Month | Planned | Status |
|-------|---------|--------|
| May 2026 | Python golden + reproduce EMG number | ✅ Stage A 90.36%, Stage B 90.30% |
| Jun 2026 | Core RTL + co-sim; D verified | ✅ `pruning_mask.sv` + D-sweep cosim/synth PASS |
| Jul 2026 | Stream wrapper + DMA bring-up | ✅ Ahead — Phases 2–3, EMG replay PASS |
| Jul 2026 | Hook A full Python Pareto sweep | ✅ 320 rows, ~44 h (2026-07-01) |
| Aug 2026 | Twist 1/2 + baselines + INA219 power | 🔄 Tier 4 accuracy ✅; energy + twists + figure pending |
| Sep 2026 | Paper draft + DATE submit | ⏳ Not started |

---

## License

This repository's RTL, Python, and docs are the project's own work. The reproduction
depends on the third-party **HDC-EMG** dataset/code (Rahimi et al., GPLv3), fetched
separately and not redistributed here.
