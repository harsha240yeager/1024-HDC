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
| `rtl/` | SystemVerilog RTL: `xor_permute_top.sv` (1024-bit XOR+permute datapath), `permute_stage.sv` (permutation modes), `bundle_unit.sv` (majority-vote bundler), `popcount_am.sv` (nearest-prototype associative memory), `item_mem.sv` (hypervector ROM), `encoder_top.sv` (EMG-window encoder), `hdc_core_top.sv` (end-to-end inference core: encoder → AM), `hdc_core_axi_lite.sv` (AXI4-Lite wrapper around the core), `hdc_stream_wrapper.sv` (AXI4-Stream wrapper for DMA-fed streaming), `simple_bind_rom.sv` (bind-vector ROM), `hdc_axi_lite_wrapper.sv` (legacy bind+permute AXI4-Lite slave). |
| `tb/` | Testbenches: `tb_xor_permute.sv` (golden-model self-checking TB), `tb_cosim.sv` (bind+permute co-sim), `tb_bundle_cosim.sv` (bundle co-sim), `tb_am_cosim.sv` (associative-memory co-sim), `tb_encoder_cosim.sv` (encoder co-sim), `tb_core_cosim.sv` (end-to-end inference co-sim), `tb_core_axi_cosim.sv` (AXI4-Lite-driven inference co-sim), and `tb_stream_cosim.sv` (AXI4-Stream co-sim with random gaps + back-pressure) — the co-sim TBs check the RTL bit-for-bit against the Python golden vectors. |
| `sim/` | Automation: `run_cosim.do` (bind+permute), `run_bundle_cosim.do` (bundle), `run_am_cosim.do` (associative memory), `run_encoder_cosim.do` (encoder), `run_core_cosim.do` (end-to-end inference), `run_core_axi_cosim.do` (AXI4-Lite), and `run_stream_cosim.do` (AXI4-Stream) — one-command harnesses (generate vectors → compile → simulate → PASS/FAIL); `open_project.do` opens the GUI project. |
| `sw/` | Bare-metal software: `hdc_core_axi_example.c` (smoke test), `hdc_core_golden_test.c` (200-case board golden test), `hdc_core_bench.c` (Phase 1 latency + golden bench), `hdc_core_regs.c/h`, and generated `golden_vectors.h`. |
| `docs/` | Research plan, advisor one-pager, project guide, and the reference paper (PDF/HTML/DOCX). |
| `python_ref/` | Bit-exact Python golden reference, EMG reproduction (Stage A/B), frozen baseline config + results, and PDF notes. See `python_ref/README.md`. |
| `scripts/` | Golden-test prep (`prep_golden_test.sh`, `.ps1`), on-board JTAG runner (`run_golden_jtag.tcl`, `run_golden_jtag.sh`), Phase 1 bench (`run_bench_hdc.sh`, `build_hdc_core_bench.sh`). |
| `vivado_pack/` | Vivado bring-up bundle (RTL, cosim vectors layout, bare-metal examples). See `vivado_pack/README.txt`. |
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

The end-to-end core has its own harness (trained prototypes + pruning mask
loaded once, then level grid in → class label out):

```bash
vsim -c -do sim/run_core_cosim.do
```

The AXI4-Lite wrapper has its own harness — a SystemVerilog AXI master drives
the real register-map programming sequence (staging-buffer prototype/mask loads,
then per-window START / poll DONE / read RESULT):

```bash
vsim -c -do sim/run_core_axi_cosim.do
```

The AXI4-Stream wrapper has its own harness — each window streamed as 3 TDATA
beats with random idle gaps, results consumed under random back-pressure:

```bash
vsim -c -do sim/run_stream_cosim.do
```

For **functional verification with trace + waveform** (recommended while learning
the streaming path):

```bash
vsim -c -do sim/run_stream_cosim_debug.do
```

This enables `+DEBUG +TRACE=3 +WAVE`, prints every handshake/FSM transition, and
writes `sim/waves/stream_cosim.vcd`. Key signals: `s_axis_*`, `m_axis_*`,
`dut/dbg_fsm_state`, `dut/dbg_core_*`, and inside the core
`dut/u_core/u_encoder/*`, `dut/u_core/u_am/*`.

See `docs/AXI4_Lite_Protocol_Study.pdf` and `docs/AXI4_Stream_Protocol_Study.pdf`
for from-scratch explanations of the two protocols, and the matching
`docs/HDC_Core_AXI_Lite_and_Cosim_Flow.pdf` / `docs/HDC_Stream_Wrapper_and_Cosim_Flow.pdf`
for each wrapper's design + co-sim flow.

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

### ZedBoard golden test (200 cases, seed 42)

Requires a programmed bitstream whose `item_mem_*.mem` ROMs were built from the
same `python_ref/vectors/cosim_core/` vectors (seed 42). Regenerate vectors and
the C header from the repo root:

```bash
bash scripts/prep_golden_test.sh
```

On Windows:

```powershell
powershell -File scripts/prep_golden_test.ps1
```

This produces `sw/golden_vectors.h` (200 cases). Vitis app sources:
`sw/hdc_core_golden_test.c`, `sw/hdc_core_regs.c`, `sw/golden_vectors.h`
(add `sw/` to the include path). Base address: `0x43C00000`.

#### Option A — JTAG golden test (recommended on VDI; no UART)

Uses xsdb to drive the HDC registers and compare against `core_expect.hex`
(same flow as `tb/tb_core_axi_cosim.sv`). Requires the **Final HDC** Vitis
workspace on the same machine (bitstream + FSBL + `program_pl_only.tcl`).

From the Final HDC workspace:

```bash
bash "/home/bsp-lab/Desktop/Final HDC/HDC_harsha/run_final_1024_hdc.sh" --golden-jtag
```

Or from this repo (sets `HDC_ROOT` to the Final HDC workspace by default):

```bash
bash scripts/run_golden_jtag.sh
```

Override paths if needed:

```bash
export HDC_ROOT="/path/to/Final HDC/HDC_harsha"
export HDC_GOLDEN_VECDIR="/path/to/1024-HDC/python_ref/vectors/cosim_core"
export HDC_LOG_DIR="/tmp/golden_jtag_hdc"
bash scripts/run_golden_jtag.sh
```

Success:

```
PASS: 200/200 golden cases
```

Logs: `$HDC_LOG_DIR/golden_*_attempt_*.log` (default `/tmp/golden_jtag_hdc/` or
`/tmp/final_1024_hdc/` when using `run_final_1024_hdc.sh`).

#### Option B — Bare-metal app + UART

Build the golden-test ELF in Vitis, program the board, launch on hardware, and
open serial **115200 8N1 before Resume**. Expect:

```
PASS: 200/200 golden cases
```

Note: on ZedBoard the Digilent USB cable shares JTAG and UART — you cannot
capture UART while JTAG is active. Use Option A if serial capture is unreliable.

#### Smoke test (single case, JTAG register read)

After programming with `hdc_core_axi_example.c`:

```bash
bash "/home/bsp-lab/Desktop/Final HDC/HDC_harsha/run_final_1024_hdc.sh" --read-only
```

Expected: class **3**, distance **623**, `SMOKE TEST: PASS`.

### Phase 1 board bench (1000 timed inferences + 200-case golden)

`sw/hdc_core_bench.c` times **1000** START→DONE inference loops (AXI-Lite poll),
prints min/max/mean latency, then runs the **200/200 golden check** in the same
run. Results are published to DDR `0x00100000` for JTAG readback (magic
`0xBEC00001`, D-cache flushed so xsdb `mrd` sees them).

Regenerate vectors first:

```bash
bash scripts/prep_golden_test.sh
```

Build the bench ELF (manual gcc link; same BSP as smoke/golden):

```bash
bash scripts/build_hdc_core_bench.sh
```

Run on ZedBoard (single xsdb session — CPU stays running during poll):

```bash
bash scripts/run_bench_hdc.sh
```

Or from the Final HDC workspace:

```bash
bash "/home/bsp-lab/Desktop/Final HDC/HDC_harsha/run_bench_hdc.sh"
```

Results are saved to `results/phase1_board.txt`. Success:

```
PASS: 200/200 golden cases
```

Example latency line (ZedBoard, AXI-Lite @ 100 MHz PL):

```
min  = 3 us
max  = 3 us
mean = 3 us
```

## Roadmap (June+)

- ~~Automated bind+permute co-sim harness driven by the Python golden~~ — **done** (`sim/run_cosim.do`).
- ~~`bundle_unit.sv` (majority bundler) + co-sim~~ — **done** (`sim/run_bundle_cosim.do`, 500/500 PASS). See `docs/Bundle_Unit_and_Cosim_Flow.pdf`.
- ~~`popcount_am.sv` (nearest-prototype associative memory) + co-sim~~ — **done** (`sim/run_am_cosim.do`, 500/500 PASS). See `docs/Popcount_AM_and_Cosim_Flow.pdf`.
- ~~`item_mem.sv` + `encoder_top.sv` (full EMG-window encoder) + co-sim~~ — **done** (`sim/run_encoder_cosim.do`, 500/500 PASS). See `docs/Encoder_Top_and_Cosim_Flow.pdf`.
- ~~`hdc_core_top.sv` (encoder → AM + pruning mask, end-to-end inference) + co-sim~~ — **done** (`sim/run_core_cosim.do`, 500/500 PASS). See `docs/HDC_Core_Top_and_Cosim_Flow.pdf`.
- ~~`hdc_core_axi_lite.sv` (AXI4-Lite control wrapper around the core) + co-sim~~ — **done** (`sim/run_core_axi_cosim.do`, 200/200 PASS). See `docs/HDC_Core_AXI_Lite_and_Cosim_Flow.pdf` and the protocol study `docs/AXI4_Lite_Protocol_Study.pdf`.
- ~~`hdc_stream_wrapper.sv` (AXI4-Stream wrapper for DMA-fed streaming) + co-sim~~ — **done** (`sim/run_stream_cosim.do`, 200/200 PASS under random gaps + back-pressure). See `docs/HDC_Stream_Wrapper_and_Cosim_Flow.pdf` and the protocol study `docs/AXI4_Stream_Protocol_Study.pdf`.
- ~~Zynq bring-up: Vivado block design (PS + AXI-DMA + both wrappers), on-board smoke test, then throughput / latency / energy / area measurements.~~ — **smoke + 200-case JTAG golden test + Phase 1 latency bench done** on ZedBoard (see ZedBoard golden test and Phase 1 bench above).
- Novelty studies: dimension/precision/pruning Pareto (Hook A), informed-vs-random pruning (Twist 1), cross-subject mask transfer (Twist 2).

## License / attribution

This repo's own RTL, Python, and docs are the project's work. The reproduction
depends on the third-party **HDC-EMG** repository (Rahimi et al., GPLv3), which is
fetched separately and not redistributed here.
