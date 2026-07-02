# 1024-HDC — Streaming Hyperdimensional Computing on Zynq

A 1024-bit Hyperdimensional Computing (HDC) classifier in SystemVerilog for the
Xilinx Zynq-7020 (ZedBoard), **bit-exact verified** against a Python golden
reference and validated on silicon with EMG hand-gesture recognition under the
frozen protocol **P-may2026**.

The core implements **XOR bind**, **permute** (cyclic shift), **majority bundle**,
and **masked Hamming / popcount** associative-memory search on 1024-bit binary
hypervectors (Binary Spatter Code model). It is controlled from the PS over
**AXI4-Lite** and fed at inference rate over **AXI4-Stream + DMA**.

> **Target venue:** DATE 2027 (~Sep 2026 submission).
> **Contribution:** a three-axis accuracy / energy / area Pareto study
> (dimension × bundle precision × bit-pruning), plus informed-vs-random pruning
> and cross-subject mask transfer on measured Zynq energy — *not* a re-port of
> prior FPGA-HDC accuracy.

**Platform:** ZedBoard `xc7z020clg484-1` @ 100 MHz PL · Vivado 2024.2 · ModelSim/Questa
**Repo:** [`harsha240yeager/1024-HDC`](https://github.com/harsha240yeager/1024-HDC)

---

## Contents

- [Status](#status)
- [Results](#results)
- [Accuracy: the two-baseline story](#accuracy-the-two-baseline-story)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Energy measurement](#energy-measurement)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## Status

*Last updated: July 2026.*

**Done:** RTL verification · Phases 1–3 Zynq bring-up · D-sweep · Hook A Python sweep
(320 rows) · comparison baselines (ARM HDC + MLP) · **INA219 energy at anchors A/B/C + ARM**
(3× each, pooled Fisher mask, 2026-07-02).

**Next:** On-board anchor EMG replays (A/B/C) · Hook A Pareto figure · Twist 1/2 · DATE draft.

| Area | State |
|------|-------|
| RTL + 9 co-sim harnesses + `pruning_mask` | ✅ Bit-exact vs Python |
| D-sweep cosim + OOC synth — D ∈ {256, 512, 1024, 2048} | ✅ [`results/dsweep/`](results/dsweep/) |
| Phase 1 — AXI-Lite | ✅ 200/200 golden, ~3 µs/window |
| Phase 2 — AXI-DMA stream | ✅ 200/200 golden, ~7 µs/window |
| Phase 3 — SG batch + EMG replay | ✅ ~216k win/s · **74.24%**, 658k windows, Δ0.00% |
| Hook A — Python sweep (D × CNT_W × pruning) | ✅ 64 configs × 5 subjects |
| INA219 energy — anchors A/B/C + ARM | ✅ PL **~12 µJ/w** · ARM **~2088 µJ/w** · [`energy_summary.txt`](results/phase3/energy_summary.txt) |
| ARM HDC baseline | ✅ 74.15% · 819 µs/window · 200/200 golden |
| Tiny int8 MLP baseline | ✅ 93.01% float / 92.99% int8 |
| On-board anchor EMG replays (A/B/C) | ⏳ Pending |
| Twist 1 · Twist 2 | ⏳ Not started |

---

## Results

All board numbers: ZedBoard `xc7z020clg484-1` @ 100 MHz PL (Vivado 2024.2).
Raw logs: [`results/`](results/).

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

### D-sweep — area axis (OOC synthesis)

| D | Slice LUT | LUT util | WNS (ns) | Fmax | Cosim |
|---|-----------|----------|----------|------|-------|
| 256 | 7,331 | 13.8% | 1.669 | 120 MHz | PASS |
| 512 | 14,422 | 27.1% | 1.452 | 117 MHz | PASS |
| 1024 | 28,600 | 53.8% | 0.781 | 109 MHz | PASS |
| 2048 | 59,261 | 111% | 1.340 | 116 MHz | PASS |

LUT/FF scale ~linearly with D. **D=1024** is timing-tightest (WNS 0.781 ns) but meets 100 MHz.
**D=2048** exceeds xc7z020 LUT budget — a reportable Pareto boundary.
Full reports: [`results/dsweep/`](results/dsweep/).

### Hook A — Python accuracy sweep

RTL-matched `hdc_ref` encoder · **P-may2026** · 5 subjects · informed Fisher masks ·
area from [`results/dsweep/`](results/dsweep/).

```bash
python3 python_ref/run_hook_a_sweep.py --quick   # sanity (~3 min)
python3 python_ref/run_hook_a_sweep.py           # full grid (~44 h)
```

Grid: **D** ∈ {256, 512, 1024, 2048} × **CNT_W** ∈ {3, 4, 5, 6} × **keep** ∈ {1.0, 0.5, 0.25, 0.125}.
Outputs: [`results/hook_a/sweep_summary.csv`](results/hook_a/sweep_summary.csv).

**Headline (5 subjects, informed Fisher mask):**

| Reference | Spatial mean |
|-----------|--------------|
| D=1024, CNT_W=6, keep=1.0 (Python spatial mean) | **74.15%** |
| Board RTL EMG replay (keep=1.0) | **74.24%** |
| Best grid point (D=2048, CNT_W≥4) | **77.62%** (59k LUT — OOC only) |
| CNT_W=3 (all D) | **59.48%** (bundle-precision floor) |

At **D=1024, CNT_W≥4**, accuracy is **flat at 74.15%** from 0% → **87.5%** pruning.
Measured J21 energy at anchors A/B/C is also **flat ~12 µJ/w** (static-dominated; see [Energy](#energy-measurement)).

**Silicon anchor picks** (D=1024, reprogram pruning mask before each run):

| Anchor | keep | Prune | Hook A target | Measured µJ/w | Role |
|--------|------|-------|---------------|---------------|------|
| **A** — baseline | 1.0 | 0% | 74.15% | 11.98 ± 0.07 | Full mask (keep=1.0 = all-ones) |
| **B** — knee | 0.5 | 50% | 74.15% | 11.90 ± 0.04 | Pooled Fisher on silicon |
| **C** — aggressive | 0.125 | 87.5% | 74.15% | 11.81 ± 0.12 | Max prune; board PASS vs export ref |

**Mask note:** Hook A Python uses **per-subject** Fisher masks; silicon uses one **pooled**
Fisher mask (`patch_emg_anchor.py`). At keep=1.0 both are all-ones; at B/C bit patterns
can differ — document measured board accuracy in Limitations if needed.

Full table: [`results/hook_a/README.md`](results/hook_a/README.md).

### Comparison baselines

Same **P-may2026** protocol. Details: [`results/baselines/`](results/baselines/).

| Baseline | Accuracy | Latency | Energy (12 V, J21) |
|----------|----------|---------|---------------------|
| **PL DMA batch** (reference) | **74.24%** | ~4 µs/window | **11.98 ± 0.07 µJ/w** (anchor A) |
| **ARM HDC** (`hdc_arm_ref.c`) | 74.15% | 819 µs/window | **2088 ± 6 µJ/w** |
| Tiny int8 MLP (~5.8k params) | 93.01% / 92.99% int8 | — | — |
| AXI-Lite PL path | — | ~3 µs/window | — |

PL vs ARM: **~200×** faster latency · **~175×** lower energy (batch amortized, n=3 each).
Energy: [`results/phase3/energy_summary.txt`](results/phase3/energy_summary.txt).

Runners: [`run_arm_hdc_baseline.py`](python_ref/run_arm_hdc_baseline.py),
[`run_mlp_baseline.py`](python_ref/run_mlp_baseline.py),
[`run_baselines.py`](python_ref/run_baselines.py).

### Board bring-up paths

| | Phase 1 — AXI-Lite | Phase 2 — DMA | Phase 3 — SG batch |
|--|--------------------|---------------|---------------------|
| Golden | 200/200 | 200/200 | 200/200 |
| Latency | 3 µs/w | 7 µs/w | 58 µs single · ~4 µs/w batch |
| Throughput | ~333k win/s | ~143k win/s | ~216k win/s |
| WNS @ 100 MHz | +0.246 ns | +0.023 ns | +0.111 ns |

Post-route utilisation (Phase 2/3): **35,206 LUT (66%)**, **27,639 FF**, **0 DSP**, **0 BRAM**.

### EMG replay on silicon

| Metric | Value |
|--------|-------|
| Windows (5 subjects, TEST split) | 658,004 |
| Board accuracy | **74.24%** |
| vs Python golden | **Δ0.00%** → PASS |

Evidence: [`results/phase3/board_emg_replay.txt`](results/phase3/board_emg_replay.txt).

---

## Accuracy: the two-baseline story

This project reports **two accuracy numbers on purpose**.

| Track | Where | Encoding | Accuracy | Role |
|-------|-------|----------|----------|------|
| Stage A — MAP parity | Python | Bipolar MAP, D=10k | 90.36% | Literature parity |
| Stage B — BSC reference | Python | 4-channel records | 90.30% ± 0.13 | Frozen baseline @ D=1024 |
| **RTL encoder** | Python + **ZedBoard** | Eq. (3.1) 4×5 grid | **74.24%** | **Verified deployment path** |

The silicon runs a *hardware-faithful encoder*, not Rahimi's spatial-record encoding —
identical accuracy was never expected. The deliverable is **verification fidelity**
(Δ0.00% over 658k windows) and a **systems study** (throughput, area, measured energy).
All headline claims are **relative** to the 74.24% baseline.

Rationale: [`docs/Baseline_vs_RTL_Encoder.md`](docs/Baseline_vs_RTL_Encoder.md).
Silicon gate: `|board_acc − export_ref| ≤ 0.5%`.

---

## Repository layout

| Path | Contents |
|------|----------|
| `rtl/` | Datapath: bind, permute, bundle, `pruning_mask`, AM, encoder, AXI wrappers |
| `sim/` | One-command co-sim harnesses (`run_*_cosim.do`) |
| `sw/` | Bare-metal drivers, `hdc_arm_ref.c`, `hdc_arm_bench.c` |
| `python_ref/` | Golden model, Hook A sweep, baseline runners |
| `scripts/` | Golden prep, energy campaign, `ina219_log.py`, `patch_emg_anchor.py` |
| `board/HDC_DMA/` | Vitis workspace, JTAG scripts, anchor replay |
| `results/` | Phase logs, [`hook_a/`](results/hook_a/), [`baselines/`](results/baselines/), [`phase3/`](results/phase3/) |
| `docs/` | Research plan, encoder rationale, protocol PDFs |

Third-party HDC-EMG data (`python_ref/HDC-EMG/`, GPLv3) and co-sim vectors are not
committed — reproducible via clone + `run_*_cosim.do`.

---

## Quick start

### RTL co-simulation

```bash
vsim -c -do sim/run_core_cosim.do          # end-to-end core
vsim -c -do sim/run_stream_cosim.do          # AXI4-Stream path
vsim -c -do sim/run_dsweep_cosim.do          # D-sweep functional
vivado -mode batch -source scripts/dsweep_synth.tcl
```

### Python golden + Hook A

```bash
cd python_ref && pip install -r requirements.txt
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG   # one-time
python run_smoke_test.py
python run_hook_a_sweep.py --quick
```

### ZedBoard (Phase 3)

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
cd board/HDC_DMA && bash build_sw.sh
bash run_phase3_bench.sh    # → results/phase3/board_bench.txt
bash run_phase3_emg.sh      # → results/phase3/board_emg_replay.txt
```

### Anchor EMG replay (pending on silicon)

```bash
bash board/HDC_DMA/run_anchor_replay.sh ALL   # A → B → C
```

### Energy campaign (INA219 + Pi)

```bash
source results/phase3/energy_cal.env
bash scripts/run_energy_only.sh               # full A→B→C→ARM campaign
bash scripts/run_after_energy_review.sh       # golden_expect + EMG anchor prep
```

Full wiring and workflow: [Energy measurement](#energy-measurement).

---

## Energy measurement

Whole-board **12 V input** via ZedBoard **J21** (10 mΩ shunt) + [INA219](https://www.adafruit.com/product/904)
on a **Raspberry Pi** (I²C). Ubuntu runs JTAG/bench over USB — **two-machine** workflow.

**Wiring and safety:** [`results/phase3/energy_setup.md`](results/phase3/energy_setup.md)

### Measured results (2026-07-02, n=3 per anchor)

Pooled Fisher mask — same bytes in `sw/golden_vectors.h` and `sw/emg_board_vectors.h`.
Batch integration via `scripts/ina219_log.py --integrate-mode batch`
(scales by measured batch duration, **not** full 30 s log ÷ 200).

| Anchor | Path | keep | Static (mW) | Total (µJ/w) | Batch slot |
|--------|------|------|-------------|--------------|------------|
| **A** | PL DMA | 1.0 | 2586 ± 17 | **11.98 ± 0.07** | ~0.93 ms / 200 win |
| **B** | PL DMA | 0.5 | 2570 ± 8 | **11.90 ± 0.04** | ~0.93 ms / 200 win |
| **C** | PL DMA | 0.125 | 2551 ± 25 | **11.81 ± 0.12** | ~0.93 ms / 200 win |
| **ARM** | PS software | 1.0 | 2553 ± 8 | **2088 ± 6** | ~164 ms / 200 win |

Summary: [`results/phase3/energy_summary.txt`](results/phase3/energy_summary.txt) ·
Per-run CSVs: [`results/phase3/energy_runs/anchor_*/`](results/phase3/energy_runs/).

**How to read:** total µJ/w ≈ `P_static × t_batch / 200`. PL total is **static-dominated**
(A/B/C flat within noise). ARM/PL **~175×** energy ratio tracks batch **duration** ratio.
Dynamic increment is noisy at 100 Hz sampling — not used as headline.

### Pi setup (one-time)

```bash
sudo raspi-config    # I2C → Enable
pip3 install smbus2
git clone https://github.com/harsha240yeager/1024-HDC.git ~/1024-HDC
bash scripts/energy_preflight.sh   # must PASS
```

### Scripts

| Script | Role |
|--------|------|
| [`run_energy_only.sh`](scripts/run_energy_only.sh) | Full campaign (A→B→C→ARM, 3× each) |
| [`run_energy_one_run.sh`](scripts/run_energy_one_run.sh) | Single run |
| [`run_energy_log_pi.sh`](scripts/run_energy_log_pi.sh) | Pi logger (manual) |
| [`run_phase3_bench_load_energy.sh`](board/HDC_DMA/run_phase3_bench_load_energy.sh) | PL bench trigger |
| [`run_arm_bench_load_energy.sh`](board/HDC_DMA/run_arm_bench_load_energy.sh) | ARM bench trigger |
| [`patch_emg_anchor.py`](scripts/patch_emg_anchor.py) | Reprogram Fisher mask per anchor |

Calibration: `source results/phase3/energy_cal.env` (`SHUNT_MOHM=10`, `CAL_REF_MV=2.0`).

---

## Limitations

| Topic | Note |
|-------|------|
| PL total energy | Static-dominated; pruning cuts **area** but not measured J21 µJ/w |
| Dynamic increment | Burst (~926 µs) undersampled @ 100 Hz — noisy |
| Measurement scope | Whole-board 12 V @ J21, not Vcc_int-only |
| Hook A grid | 64 Python configs; **four measured** silicon points (A/B/C/ARM) |
| Subjects | 5 in Hook A; Twist 2 pilot scale |
| 74% vs ~90% | Different encoder by design — see [two-baseline story](#accuracy-the-two-baseline-story) |
| Fisher masks | Hook A Python: **per-subject** Fisher; silicon: **pooled** Fisher — same at keep=1.0, may differ at B/C |
| Lab hardware | Pi + INA219 **not required** for remaining critical path — reconnect only for optional dynamic-power logging or re-measurement |

Do **not** use legacy full-log integration (~2240 µJ/w) — wrong ~190×.
---

## Roadmap

### Now

- [x] INA219 energy — anchors A/B/C + ARM (3× each, 2026-07-02)
- [ ] On-board EMG replay at anchors A/B/C — `bash board/HDC_DMA/run_anchor_replay.sh ALL`
  (Hook A targets ~74.15%; board PASS vs export ref; see [`anchors/README.md`](results/phase3/anchors/README.md))
- [ ] Hook A Pareto figure — accuracy × LUT × measured µJ

### Then

- [ ] **Twist 1** — informed vs random @ D=1024, keep=0.5 (target ≥5 pp)
- [ ] **Twist 2** — cross-subject mask transfer (pilot, 5 subjects)

### Paper (Sep 2026)

- [ ] Figures + DATE draft — Pareto, twists, Fisher heatmap, baseline table, limitations

| Month | Planned | Status |
|-------|---------|--------|
| May–Jun 2026 | Golden + RTL + D-sweep | ✅ |
| Jul 2026 | DMA bring-up + Hook A sweep | ✅ |
| Aug 2026 | INA219 + twists + figures | 🔄 Energy ✅ · EMG anchors + Pareto pending |
| Sep 2026 | DATE draft | ⏳ |

---

## License

RTL, Python, and docs are the project's own work. Depends on third-party
**HDC-EMG** (Rahimi et al., GPLv3), fetched separately and not redistributed here.
