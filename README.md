# 1024-HDC — 1024-bit Hyperdimensional Computing block on Zynq

A 1024-bit Hyperdimensional Computing (HDC) processing block in SystemVerilog,
targeting a Xilinx Zynq SoC, with a bit-exact Python golden reference and a
reproduced EMG hand-gesture classification baseline.

The hardware core performs the HDC primitives — **XOR bind**, **permute**
(cyclic shift), **majority bundle**, and **Hamming/popcount** associative-memory
search — on 1024-bit binary hypervectors (Binary Spatter Code model), exposed to
the PS through an AXI4-Lite wrapper.

## Repository layout

| Folder | Contents |
|---|---|
| `rtl/` | SystemVerilog RTL: `xor_permute_top.sv` (1024-bit XOR+permute datapath), `permute_stage.sv` (permutation modes), `bundle_unit.sv` (majority-vote bundler), `popcount_am.sv` (nearest-prototype associative memory), `item_mem.sv` (hypervector ROM), `encoder_top.sv` (EMG-window encoder), `simple_bind_rom.sv` (bind-vector ROM), `hdc_axi_lite_wrapper.sv` (AXI4-Lite slave). |
| `tb/` | Testbenches: `tb_xor_permute.sv` (golden-model self-checking TB), `tb_cosim.sv` (bind+permute co-sim), `tb_bundle_cosim.sv` (bundle co-sim), `tb_am_cosim.sv` (associative-memory co-sim), and `tb_encoder_cosim.sv` (encoder co-sim) — the co-sim TBs check the RTL bit-for-bit against the Python golden vectors. |
| `sim/` | Automation: `run_cosim.do` (bind+permute), `run_bundle_cosim.do` (bundle), `run_am_cosim.do` (associative memory), and `run_encoder_cosim.do` (encoder) — one-command harnesses (generate vectors → compile → simulate → PASS/FAIL); `open_project.do` opens the GUI project. |
| `sw/` | Bare-metal software: `hdc_axi_example.c` (Zynq PS example driving the AXI-Lite core). |
| `docs/` | Research plan, advisor one-pager, project guide, and the reference paper (PDF/HTML/DOCX). |
| `python_ref/` | Bit-exact Python golden reference, EMG reproduction (Stage A/B), frozen baseline config + results, and PDF notes. See `python_ref/README.md`. |
| `1024HDC.mpf`, `modelsim.ini` | ModelSim/Questa project files (kept at repo root; source paths point into `rtl/` and `tb/`). |

> The reference paper's code/data (`python_ref/HDC-EMG/`, GPLv3) and the generated
> co-simulation vectors (`python_ref/vectors/`) are **not** committed — see
> `.gitignore`. Both are reproducible (clone the repo / run `generate_vectors.py`).

## What's done (May 2026 milestone — software golden path locked)

- **RTL core + self-checking testbench** for the 1024-bit XOR+permute datapath.
- **Python golden reference** (`python_ref/hdc_ref.py`) matching RTL semantics, with smoke tests.
- **EMG baseline reproduced** (anchor: Rahimi et al., ICRC 2016):
  - **Stage A** — literal MAP parity: spatial **90.36%** (paper 90.8%), spatiotemporal **96.04%** (paper 97.8%).
  - **Stage B** — RTL-matched binary BSC model, D-sweep.
- **Frozen project baseline:** **90.30% ± 0.13 (spatial)** at **D=1024** under protocol P-may2026
  (`python_ref/config/emg_baseline.json`, `python_ref/results/emg_baseline.json`).

Details: `python_ref/notes/emg_baseline_frozen.pdf` and `emg_reproduction_results.pdf`.

## Quick start

### Simulation (ModelSim/Questa)

Open `1024HDC.mpf` in ModelSim, or from a shell:

```tcl
vlib work
vlog rtl/xor_permute_top.sv rtl/permute_stage.sv rtl/simple_bind_rom.sv tb/tb_xor_permute.sv
vsim work.tb_xor_permute -do "run -all"
```

### Automated co-simulation vs the Python golden

One command regenerates the golden vectors, compiles the RTL + co-sim TB, runs
the simulation, and reports PASS/FAIL (non-zero exit on any mismatch). Run from
the repo root:

```bash
vsim -c -do sim/run_cosim.do
```

Override the case count with the `NUM_CASES` environment variable (default 1000).
The harness compares `xor_permute_top` output bit-for-bit against vectors emitted
by `python_ref/generate_vectors.py --flat`, so the Python reference is the single
source of truth (no hand-written SV golden in the loop).

The bundler has its own harness (majority bundle of K random vectors per case):

```bash
vsim -c -do sim/run_bundle_cosim.do
```

The associative memory has its own harness (masked Hamming search over N_CLASS
prototypes, including forced-tie and all-ones-mask cases):

```bash
vsim -c -do sim/run_am_cosim.do
```

The encoder has its own harness (full window encode: item-memory lookups →
bind+permute → majority bundle → query hypervector):

```bash
vsim -c -do sim/run_encoder_cosim.do
```

### Python golden reference + EMG baseline

```bash
cd python_ref
pip install -r requirements.txt
# (one-time) fetch the reference data/code:
git clone https://github.com/abbas-rahimi/HDC-EMG HDC-EMG

python run_smoke_test.py                 # verify the golden model
python run_emg_baseline.py               # frozen baseline: 5 seeds + MAP parity (~50 s)
python run_emg_baseline.py --quick --no-parity   # fast sanity (~7 s)
```

## Roadmap (June+)

- ~~Automated bind+permute co-sim harness driven by the Python golden~~ — **done** (`sim/run_cosim.do`).
- ~~`bundle_unit.sv` (majority bundler) + co-sim~~ — **done** (`sim/run_bundle_cosim.do`, 500/500 PASS). See `docs/Bundle_Unit_and_Cosim_Flow.pdf`.
- ~~`popcount_am.sv` (nearest-prototype associative memory) + co-sim~~ — **done** (`sim/run_am_cosim.do`, 500/500 PASS). See `docs/Popcount_AM_and_Cosim_Flow.pdf`.
- ~~`item_mem.sv` + `encoder_top.sv` (full EMG-window encoder) + co-sim~~ — **done** (`sim/run_encoder_cosim.do`, 500/500 PASS). See `docs/Encoder_Top_and_Cosim_Flow.pdf`.
- `hdc_core_top.sv` (encoder → AM + pruning mask, end-to-end inference) and `hdc_stream_wrapper.sv` (AXI-Stream + DMA); extend the co-sim to each.
- Novelty studies: dimension/precision/pruning Pareto (Hook A), informed-vs-random pruning (Twist 1), cross-subject mask transfer (Twist 2).
- Zynq bring-up: throughput / latency / energy / area.

## License / attribution

This repo's own RTL, Python, and docs are the project's work. The reproduction
depends on the third-party **HDC-EMG** repository (Rahimi et al., GPLv3), which is
fetched separately and not redistributed here.
