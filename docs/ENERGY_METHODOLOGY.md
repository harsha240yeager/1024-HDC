# Energy measurement methodology (ZedBoard J21 + INA219)

**Purpose:** Document how batch energy per window is measured for the DATE manuscript  
(PL DMA vs ARM software HDC; silicon anchors A/B/C).  
**Issue:** [#8](https://github.com/harsha240yeager/1024-HDC/issues/8)  
**Evidence:** [`results/phase3/energy_summary.txt`](../results/phase3/energy_summary.txt),  
[`results/phase3/energy_runs/`](../results/phase3/energy_runs/),  
[`scripts/ina219_log.py`](../scripts/ina219_log.py),  
[`results/phase3/energy_setup.md`](../results/phase3/energy_setup.md)

> **Claim boundary.** We report **whole-board 12 V input energy** at the ZedBoard  
> J21 sense tap. Runtime Fisher masks do **not** reduce measured J21 µJ/window on  
> this fixed-width datapath. The PL vs ARM ≈175× factor is a **platform / latency**  
> comparison, not a pruning benefit.

---

## 1. What is measured

| Quantity | Definition |
|----------|------------|
| Sense point | ZedBoard **J21** across the on-board **10 mΩ** shunt in the **12 V** input path ([HW UG §2.11.1](https://files.digilent.com/resources/programmable-logic/zedboard/ZedBoard_HW_UG_v2_2.pdf)) |
| Scope | Entire board input: PS + PL + DDR + I/O + regulators (not isolated VCCINT) |
| Sensor | Texas Instruments **INA219** (Adafruit breakout), I²C address **0x40** |
| Host | Raspberry Pi (I²C) coordinating with Ubuntu/JTAG bench, or USB–I²C on the bench host |
| Primary metric | **Total energy per window** \(E_{\mathrm{tot}}/N\) (µJ/w) |
| Secondary | Dynamic increment \(E_{\mathrm{dyn}}/N\) after idle subtraction (often ≪ total; noisy) |

We do **not** claim PL-rail-only or clock-gated popcount energy. Masked Hamming
clears bits before popcount but the synthesized datapath still XORs full 64-bit
words each cycle, so post-route LUT count and board joules stay flat across keep
ratios (anchors A/B/C).

---

## 2. INA219 configuration

From [`scripts/ina219_log.py`](../scripts/ina219_log.py):

| Setting | Value | Meaning |
|---------|-------|---------|
| Config register | **`0x019F`** | Continuous shunt + bus; **128-sample** averaging; ≈1.1 ms conversion |
| Logging rate | ≈ **100 Hz** | Set by conversion + host read loop |
| Current LSB | 1 mA | Used in calibration formula |
| Calibration | \(\mathrm{Cal} = 0.04096 / (I_{\mathrm{LSB}} \cdot R_{\mathrm{shunt}})\) | Clamped to 16-bit |
| Default shunt | **10 mΩ** (`INA219_SHUNT_MOHM=10`) | J21 on-board |
| Bus rail | **12.0 V** (`INA219_V_RAIL`) | For reporting only; power uses \(P = V_{\mathrm{bus}} \cdot I\) |

**Config decode (0x019F):** continuous mode, PGA/BRNG defaults for ±40 mV / 16 V-class
sensing, 128× average — suitable for steady idle and batch-window mean power, not for
resolving a single ~1 ms DMA burst sample-by-sample.

### J21 sense-wire calibration

Dupont leads on J21 can attenuate the shunt voltage. One-time scale against a
multimeter at idle:

```bash
export INA219_SHUNT_MOHM=10
export INA219_CAL_REF_MV=2.0   # multimeter mV on J21 @ idle
python3 scripts/ina219_log.py --bus 1 --shunt-mohm 10 --cal-ref-mv 2.0 --duration 3
```

Gain multiplies shunt/current; bus voltage is left unchanged; power is recomputed as
\(P = |V_{\mathrm{bus}} \cdot I|\). Campaign runs used `cal_ref_mv=2.0`
(see `energy_summary.txt`).

**Do not** use `INA219_SHUNT_MOHM=100` with J21 (that is for Adafruit **inline** 100 mΩ
only) — currents would be 10× low.

---

## 3. Procedure

### 3.1 Static / idle power \(P_{\mathrm{idle}}\)

1. Program Phase~3 bitstream; leave PL idle (no DMA inference).
2. Log INA219 for **~10 s** → `ina219_static.csv`.
3. \(P_{\mathrm{idle}} = \mathrm{mean}(P(t))\) over the static log (mW).

### 3.2 Active batch

1. Start batch log (~30 s) → `ina219_batch.csv`.
2. Immediately run the bench ELF that processes **\(N = 200\)** windows:
   - PL: `board/HDC_DMA/run_phase3_bench_load_energy.sh` (DMA SG batch)
   - ARM: `board/HDC_DMA/run_arm_bench_load_energy.sh` (PS software HDC)
3. Read measured batch wall time \(t_{\mathrm{batch}}\) from `board_bench.txt`
   (typical PL ≈ **0.93 ms**, ARM ≈ **164 ms** for 200 windows).

### 3.3 Integration (batch mode — primary)

At ~100 Hz the ~0.93 ms PL burst is **undersampled**. We therefore **do not**
integrate the full 30 s CSV as batch energy. Default `integrate_mode=batch`:

\[
\begin{aligned}
E_{\mathrm{tot}} &= P_{\mathrm{idle}} \cdot t_{\mathrm{batch}}, \\
P_{\mathrm{active}} &= \text{max sliding-window mean of } P(t) \text{ during the log}, \\
E_{\mathrm{dyn}} &= \max(0,\, P_{\mathrm{active}} - P_{\mathrm{idle}}) \cdot t_{\mathrm{batch}}, \\
e_{\mathrm{tot}} &= E_{\mathrm{tot}} / N, \qquad
e_{\mathrm{dyn}} = E_{\mathrm{dyn}} / N.
\end{aligned}
\]

Units: \(P\) in mW, \(t\) in s → energy in mJ; divide by \(N\) and convert → **µJ/window**.

This matches issue wording \(E_{\mathrm{dynamic}} = (P_{\mathrm{active}} - P_{\mathrm{idle}}) \times t\)
with \(t = t_{\mathrm{batch}}\).

**Headline table numbers use \(e_{\mathrm{tot}}\)** (~12 µJ/w PL, ~2088 µJ/w ARM).
Dynamic increments are reported in summaries but are small and run-to-run noisy
for PL (often &lt;1 µJ/w).

### 3.4 Anchors and repetitions

| Anchor | Path | keep | Mask |
|--------|------|------|------|
| A | PL DMA | 1.0 | all-ones / pooled Fisher full |
| B | PL DMA | 0.5 | pooled Fisher |
| C | PL DMA | 0.125 | pooled Fisher (128 bits) |
| ARM | PS software | 1.0 | N/A (libhdc path) |

- **Repetitions in paper tables:** \(n{=}3\) independent runs per anchor  
  (mean ± sample std in `energy_summary.txt`).
- **Recommended extension (not yet in tables):** \(n \ge 10\) with 95% CI —
  scripts under `scripts/run_energy_campaign*.sh` support longer campaigns.
- Same pooled Fisher programming path as EMG replay (`golden_vectors.h` /
  `emg_board_vectors.h`).

---

## 4. Reported results (self-consistent campaign)

From [`results/phase3/energy_summary.txt`](../results/phase3/energy_summary.txt):

| Anchor | Static (mW) | Total (µJ/w) | Dynamic (µJ/w) |
|--------|-------------|--------------|----------------|
| A (keep=1.0) | 2586 ± 17 | **11.98 ± 0.07** | 0.31 ± 0.41 |
| B (keep=0.5) | 2570 ± 8 | **11.90 ± 0.04** | 0.07 ± 0.07 |
| C (keep=0.125) | 2551 ± 25 | **11.81 ± 0.12** | 0.49 ± 0.44 |
| ARM | 2553 ± 8 | **2088 ± 6** | 111 ± 61 |

**Interpretation**

- A/B/C totals are flat within ~1.5% — **mask does not save board joules**.
- Idle ≈ 2.5–2.6 W dominates; PL batch is short, so \(E_{\mathrm{tot}} \approx P_{\mathrm{idle}} t\).
- ARM is slower → much larger \(E_{\mathrm{tot}}\) at similar idle power.

### 175× / 200× footnotes

\[
\frac{e_{\mathrm{ARM}}}{e_{\mathrm{PL}}}
= \frac{2088}{11.98} \approx 174,\qquad
\frac{t_{\mathrm{ARM}}/N}{t_{\mathrm{PL}}/N}
\approx \frac{819\,\mu\mathrm{s}}{4\,\mu\mathrm{s}} \approx 205.
\]

Because \(E_{\mathrm{tot}} \approx P_{\mathrm{idle}} \cdot t_{\mathrm{batch}}\) and
\(P_{\mathrm{idle}}\) is similar for PL and ARM benches, the energy ratio tracks the
**latency ratio**. Cite **~175× energy** and **~200× latency** as platform
comparisons, not as Fisher-pruning gains.

---

## 5. ARM software path details

| Item | Value |
|------|--------|
| Core | Cortex-A9 (Zynq PS), hard-float VFPv3 |
| Compiler | `arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard` |
| Optimization (bench ELF) | **`-O0 -g`** (debug build used for energy campaign; document as-is) |
| Workload | Same 200-window batch, software encode + classify (`libhdc_arm_ref` / `hdc_arm_ref.c`) |
| Timing | Per-window mean ≈ **819 µs** from board timing logs |

PS CPU frequency is the Zynq-7020 default PS clock configuration for the Phase~3
bitstream (board BSP); we did not retune clocks for the energy campaign.

---

## 6. Reproduce

```bash
# Pi or host with INA219 on I2C
bash scripts/energy_preflight.sh
export INA219_BUS=1 INA219_SHUNT_MOHM=10 INA219_V_RAIL=12.0
export INA219_CAL_REF_MV=2.0

# Program PL, then coordinated static + batch (see energy_setup.md)
bash scripts/run_energy_measure.sh          # or run_energy_log_pi.sh + bench on Ubuntu

# Aggregate multi-run campaign
python3 scripts/aggregate_energy_runs.py
```

Raw CSVs live under `results/phase3/energy_runs/anchor_*/run*/`.

---

## 7. Limitations (for paper Discussion / appendix)

1. **Whole-board**, not PL-rail isolated power.  
2. **~100 Hz** sampling cannot resolve sub-millisecond DMA bursts; batch-duration
   scaling is required.  
3. **\(n{=}3\)** in published tables; larger \(n\) improves CI width.  
4. Mask / keep ratio does not change measured \(e_{\mathrm{tot}}\) on this RTL.  
5. Energy numbers are **split-independent** (HDC-1 vs HDC-2 accuracy reruns do not
   require energy remeasurement for the platform comparison).

---

## 8. Paper text

Methods §Energy Measurement in Research-paper `conference_101719.tex` carries the
formulas, 174×/205× footnotes, and claim boundary.
This file is the full artifact write-up (wiring, scripts, raw CSVs).
