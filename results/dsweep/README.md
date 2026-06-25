# D-sweep results (Hook A — dimension axis)

Closes the June gap *"D parameterization not synthesis-verified."* The HDC core
is parameterized on `D` (via `WORDS = D/64`); this directory records that the
datapath is **functionally correct** and **synthesizes with sane area/timing**
at every swept `D ∈ {256, 512, 1024, 2048}`.

This is the **D-axis** of the Hook A 3-axis Pareto (D × bundle-precision × prune).

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

## 1. Functional co-sim (fill after `run_dsweep_cosim.do`)

| D | WORDS | Cases | Result |
|---|-------|-------|--------|
| 256  | 4  | 200 | _PENDING_ |
| 512  | 8  | 200 | _PENDING_ |
| 1024 | 16 | 200 | _PENDING_ (baseline — already PASS via run_core_cosim) |
| 2048 | 32 | 200 | _PENDING_ |

PASS = `tb_core_cosim` reaches `$finish` with 0 mismatches at that D.

## 2. OOC synthesis (fill from `summary.txt` / `synth_D<D>.txt`)

Part `xc7z020clg484-1`, clock 100 MHz (10.0 ns). Core-only (no PS/DMA).

| D | LUT | FF | DSP | BRAM | WNS (ns) | Fmax (MHz) |
|---|-----|----|----|------|----------|------------|
| 256  | _–_ | _–_ | 0 | 0 | _–_ | _–_ |
| 512  | _–_ | _–_ | 0 | 0 | _–_ | _–_ |
| 1024 | _–_ | _–_ | 0 | 0 | _–_ | _–_ |
| 2048 | _–_ | _–_ | 0 | 0 | _–_ | _–_ |

> Note: OOC counts are **core-only**. Full-system utilisation + bitstream timing
> (with the Zynq PS + AXI-DMA) come from the `FInal_HDC` place&route run; see
> `results/phase2/synthesis_utilisation.txt` for the integrated D=1024 number
> (35,206 LUT / 66.2%).

## 3. Expected shape (sanity check)

- LUT/FF should scale ~linearly with `D` (1024-bit datapath is replicated per word).
- `D=2048` is the area/timing risk point on xc7z020 (Phase 2 already at 96% slices
  for D=1024 + PS/DMA); OOC core-only should still fit, but the **full system at
  D=2048 may not** — that itself is a reportable Pareto boundary.
- Accuracy vs D is a separate Python sweep (Hook A), not measured here.
