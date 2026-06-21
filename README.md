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
| `sw/` | Bare-metal software: `hdc_core_axi_example.c` (smoke test), `hdc_core_golden_test.c` (200-case board golden test), `hdc_core_bench.c` (Phase 1 latency + golden bench), `hdc_dma_stream*.c/h` (Phase 2 DMA path), `hdc_core_regs.c/h`, and generated `golden_vectors.h`. |
| `results/` | Board benchmarks, synthesis utilisation/timing, and per-phase logs — updated after each Vivado/board run. See `results/README.md`. |
| `docs/` | Research plan, advisor one-pager, project guide, and the reference paper (PDF/HTML/DOCX). |
| `python_ref/` | Bit-exact Python golden reference, EMG reproduction (Stage A/B), frozen baseline config + results, and PDF notes. See `python_ref/README.md`. |
| `scripts/` | Golden-test prep (`prep_golden_test.sh`), JTAG runners (`run_golden_jtag.tcl`, `run_stream_golden_jtag.tcl`), Phase 1 bench helpers. |
| `board/HDC_DMA/` | **Phase 2 ZedBoard workspace**: Vitis platform, DMA golden/bench ELFs, `run_jtag.sh`, `run_bench.sh`, JTAG Tcl. See `board/HDC_DMA/README.md`. |
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

## Board results summary (ZedBoard, xc7z020 @ 100 MHz)

Two comparable inference paths on the **same HDC core** — see `results/` for full logs.

| | Phase 1 — AXI-Lite | Phase 2 — DMA stream |
|--|--------------------|----------------------|
| **Paper role** | Baseline #2: register-mapped (shows why streaming matters) | Main path for throughput and energy |
| **Golden test** | 200/200 PASS | 200/200 PASS |
| **Latency (mean)** | **3 µs**/window | **7 µs**/window |
| **Throughput** | ~333k windows/s | ~143k windows/s |
| **WNS @ 100 MHz** | +0.246 ns | +0.023 ns |
| **Results** | `results/phase1/` | `results/phase2/` |

Phase 2 DMA latency includes channel setup + CPU busy-wait (single window per
transfer). Batch DMA (Phase 3) should improve sustained throughput.

**Phase 2 workspace:** `board/HDC_DMA/` — build, golden test, and bench scripts
are self-contained in this repo.

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

### Phase 2 — DMA stream golden + bench (ZedBoard)

Phase 2 uses `hdc_stream_system_bd_wrapper` + AXI DMA @ `0x40400000`, config @
`0x43C00000`. Software: `sw/hdc_dma_stream*.c`.

**Prerequisite:** Vivado `FInal_HDC` project on the build machine (for XSA/bitstream export):

```bash
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
cd board/HDC_DMA
bash build.sh          # BSP + FSBL + golden + bench ELFs
bash run_jtag.sh       # 200-case golden over JTAG → expect PASS: 200/200
bash run_bench.sh      # 1000-iter latency bench + golden spot-check
```

Results saved under `results/phase2/`:

| File | Content |
|------|---------|
| `board_golden.txt` | PASS 200/200 stream golden (JTAG) |
| `board_bench.txt` | 7 µs mean latency, PASS 200/200 golden spot-check |
| `synthesis_timing.txt` | WNS +0.023 ns |
| `synthesis_utilisation.txt` | 66% LUT, 96% slices |

Host-side golden Tcl (same vectors): `scripts/run_stream_golden_jtag.tcl`
(set `HDC_IDE=board/HDC_DMA/_ide`, or use `run_jtag.sh` which sets it automatically).

Bare-metal UART option: `board/HDC_DMA/run_program.sh` with serial @ 115200.

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

Results are saved to `results/phase1/board_bench.txt` (see `results/phase1/`). Success:

```
PASS: 200/200 golden cases
```

Example latency line (ZedBoard, AXI-Lite @ 100 MHz PL):

```
min  = 3 us
max  = 3 us
mean = 3 us
```

## Roadmap

### Done

- ~~Automated bind+permute co-sim harness~~ — **done** (`sim/run_cosim.do`).
- ~~`bundle_unit.sv` + co-sim~~ — **done** (500/500 PASS).
- ~~`popcount_am.sv` + co-sim~~ — **done** (500/500 PASS).
- ~~`encoder_top.sv` + co-sim~~ — **done** (500/500 PASS).
- ~~`hdc_core_top.sv` + co-sim~~ — **done** (500/500 PASS).
- ~~`hdc_core_axi_lite.sv` + co-sim~~ — **done** (200/200 PASS).
- ~~`hdc_stream_wrapper.sv` + co-sim~~ — **done** (200/200 PASS).
- ~~**Phase 1** Zynq bring-up (AXI-Lite)~~ — **done**: golden 200/200, ~3 µs/window, WNS +0.246 ns. `results/phase1/`.
- ~~**Phase 2** Zynq bring-up (DMA stream)~~ — **done**: golden 200/200, ~7 µs/window, WNS +0.023 ns. `results/phase2/`, `board/HDC_DMA/`.

### Phase 3 — measurement infrastructure (next)

Phase 2 proves **correctness**; Phase 3 produces the numbers the paper needs for
Pareto / energy claims. Record under `results/phase3/`.

| Task | Why | Status |
|------|-----|--------|
| **Stream batch bench** | Sustained windows/s with batched DMA (not one window per transfer) | Not started |
| **End-to-end latency** | Last input beat → result beat (global timer) | Not started |
| **Full dataset replay on board** | Many windows; accuracy vs Python on real EMG vectors (~0.5% target) | Not started |
| **Energy setup** | Shunt + INA219 on Vcc_int; static + dynamic over fixed batch | Not started |

Without batch throughput + energy, Hook A (Pareto) is incomplete — you would
only have accuracy and area today.

### Later

- Novelty studies (informed pruning, cross-subject transfer).
- Optional Phase 2 close-out: UART log from `hdc_dma_stream_golden_test.c`.

## License / attribution

This repo's own RTL, Python, and docs are the project's work. The reproduction
depends on the third-party **HDC-EMG** repository (Rahimi et al., GPLv3), which is
fetched separately and not redistributed here.
