# D-sweep results (Hook A — dimension axis)

Closes the June gap *"D parameterization not synthesis-verified."* The HDC core
is parameterized on `D` (via `WORDS = D/64`); this directory records that the
datapath is **functionally correct** and **synthesizes with sane area/timing**
at every swept `D ∈ {256, 512, 1024, 2048}`.

This is the **D-axis** of the Hook A 3-axis Pareto (D × bundle-precision × prune).

**Recorded:** 2026-06-25 on VDI (`bsp-lab`, Vivado 2024.2, xc7z020clg484-1 @ 100 MHz).

## How to regenerate

Functional (ModelSim/Questa — bit-exact vs Python golden, needs the USC license):

```bash
vsim -c -do sim/run_dsweep_cosim.do      # each D must print PASS
```

Synthesis (Vivado OOC — utilisation + post-synth timing per D):

```bash
vivado -mode batch -source scripts/dsweep_synth.tcl
# → results/dsweep/synth_D<D>.txt + summary.txt
```

On this VDI, functional cosim was also verified with **Vivado xsim** (Questa
license unavailable); logs are in `results/xsim_dsweep_D*.log`.

## 1. Functional co-sim

| D | WORDS | Cases | Result | Log |
|---|-------|-------|--------|-----|
| 256  | 4  | 200 | **PASS** | `results/xsim_dsweep_D256.log` |
| 512  | 8  | 200 | **PASS** | `results/xsim_dsweep_D512.log` |
| 1024 | 16 | 200 | **PASS** | `results/xsim_dsweep_D1024.log` |
| 2048 | 32 | 200 | **PASS** | `results/xsim_dsweep_D2048.log` |

PASS = `tb_core_cosim` reaches `$finish` with 0 mismatches at that D.

Related unit/integration cosim (also PASS, xsim 2026-06-25):

| Harness | Cases | Log |
|---------|-------|-----|
| `pruning_mask` | 64 | `results/xsim_pruning_mask.log` |
| `am` | 500 | `results/xsim_am.log` |
| `core` | 500 | `results/xsim_core.log` |
| `core_axi` | 200 | `results/xsim_core_axi.log` |
| `stream` | 200 | `results/xsim_stream.log` |

## 2. OOC synthesis (`summary.txt` / `synth_D<D>.txt`)

Part `xc7z020clg484-1`, clock 100 MHz (10.0 ns). Core-only (no PS/DMA).
Slice LUT/FF from Vivado utilisation report; WNS/Fmax from post-synth timing.

| D | Slice LUT | Slice FF | LUT util | DSP | BRAM | WNS (ns) | Fmax (MHz) |
|---|-----------|----------|----------|-----|------|----------|------------|
| 256  | 7,331  | 4,536  | 13.8%  | 0 | 0 | 1.669 | 120.0 |
| 512  | 14,422 | 8,935  | 27.1%  | 0 | 0 | 1.452 | 117.0 |
| 1024 | 28,600 | 17,784 | 53.8%  | 0 | 0 | 0.781 | 108.5 |
| 2048 | 59,261 | 35,424 | **111.4%** | 0 | 0 | 1.340 | 115.5 |

> **D=2048** OOC core-only exceeds xc7z020 slice LUT capacity (111%). Full-system
> D=1024 + PS/DMA already at ~66% LUT (Phase 2); integrated D=2048 is expected
> to be a Pareto boundary, not a shipping config.

> Note: OOC counts are **core-only**. Full-system utilisation + bitstream timing
> (with the Zynq PS + AXI-DMA) come from the `FInal_HDC` place&route run; see
> `results/phase2/synthesis_utilisation.txt` for the integrated D=1024 number
> (35,206 LUT / 66.2%).

## 3. Expected shape (sanity check)

- LUT/FF scale ~linearly with `D` (1024-bit datapath replicated per word) — **observed**.
- `D=1024` is the timing tightest point (WNS 0.781 ns) but still meets 100 MHz — **observed**.
- `D=2048` exceeds OOC LUT budget on xc7z020 — **observed**; reportable Pareto boundary.
- Accuracy vs D is a separate Python sweep (Hook A), not measured here.
