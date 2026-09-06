# Narrow / gated datapath (H1) — design evidence

Design-stage measurements backing [#28](https://github.com/harsha240yeager/1024-HDC/issues/28).
Full argument and micro-architecture spec: `docs/H1_narrow_datapath_design.md`.

Implementation, synthesis, and board numbers land under #29/#31 and will be added here.

## OOC synthesis (Vivado 2024.2, xc7z020clg484-1 @ 100 MHz, 2026-09-07)

Regenerate:

```bash
bash scripts/run_narrow_vs_baseline_synth.sh   # core + stream OOC
vivado -mode batch -source scripts/narrow_bd_synth.tcl   # bd-wrapper OOC
bash scripts/compare_narrow_vs_baseline_lut.sh
```

| Scope | Baseline LUT | Narrow LUT (K=128) | Δ LUT | Baseline FF | Narrow FF |
|---|---|---|---|---|---|
| Core (`hdc_core_top*`) | 28,600 | 3,794 | **−86.7%** | 17,784 | 2,209 |
| Stream wrapper | 28,963 | 4,153 | **−85.7%** | 18,960 | 3,382 |
| BD IP (`hdc_stream_system_bd_wrapper*`) | 30,639 | 4,261 | **−86.1%** | 22,117 | 3,706 |

CSV + hierarchical reports: `results/dsweep/narrow_vs_baseline_util.csv`, `synth_*_{core,stream,bd}.txt`.

Integrated place-and-route (full Zynq + DMA + bitstream):

```bash
export HDC_VIVADO_ROOT=~/Final_HDC/FInal_HDC
bash scripts/run_narrow_integrated_bitstream.sh
```

Log: `results/narrow_rtl/integrated_synth.log` · util: `integrated_utilization_placed.rpt`.

**RTL co-sim (ModelSim SE-64 10.6e, 2026-09-06, USC license):** both passes are bit-exact.

| Pass | Config | Log | Result |
|---|---|---|---|
| Identity | K=1024, SEL[i]=i, seed 31 | `identity_cosim.log` | **500/500 PASS** |
| Anchor C | K=128, Fisher keep=0.125, seed 42 | `anchor_c_cosim.log` | **500/500 PASS** |

```text
vsim -c -do sim/run_narrow_core_cosim_identity.do
vsim -c -do sim/run_narrow_core_cosim.do
```

Needs `LM_LICENSE_FILE=1715@lic-modelsim.usc.edu` (USC VPN). The `.do` files override the testbench item-memory parameters so the encoder ROMs match the vector-directory seed.

**Selected design: Option E — baked bit-permutation + narrow AM.**

## Files

| File | Produced by | What it answers |
|---|---|---|
| `mask_word_occupancy.json` | `scripts/analyze_mask_word_occupancy.py` | Do whole 64-bit words go dead under pruning? **No.** |
| `word_blocked_hdc2/` | `run_hook_a_sweep.py --mask-granularity word` | What does word-granular selection cost under HDC-2? **−2.31 pp at keep=0.25 — gate FAILED.** |
| `narrow_gather_equivalence.json` | `scripts/verify_narrow_gather_equivalence.py` | Is a baked gather bit-exact to masked full-width classify? **Yes.** |
| `word_blocked_mask_eval.json` | `scripts/eval_word_blocked_mask.py` | Superseded design proxy — **do not cite** |

## Regenerate

```bash
python3 scripts/analyze_mask_word_occupancy.py
python3 scripts/verify_narrow_gather_equivalence.py --max-windows 20000

# word-blocked gate (~1 h, full HDC-2 protocol)
python3 python_ref/run_hook_a_sweep.py --D 1024 --cnt-w 6 --keep 1.0 0.5 0.25 0.125 \
    --mask-granularity word --emg-config python_ref/config/emg_baseline_v2.json \
    --out-dir results/narrow_rtl/word_blocked_hdc2
```

The two cached-cohort scripts need `results/protocol_v2/twist1_silicon/cohort_cache.npz`; build it
with `python3 python_ref/predict_twist1_silicon_seeds.py --from-dataset`.

## Headline findings

**1. Scattered masks never free a word.** Zero dead 64-bit words at every keep ratio, for the value-table
active support, random iso-density masks (seeds 0–9), and Fisher-ranked masks. Kept bits are uniformly
scattered because the item memory is random, so any skip-the-dead-word optimisation saves exactly 0%.
This refutes both the naive word-skip and the runtime-skip variants.

**2. Word-blocked selection fails the accuracy gate.** HDC-2, D=1024, cnt_w=6, 5 subjects, TRAIN-derived
Fisher, all windows. Compared against free-choice on the same `spatial_mean_accuracy` statistic:

| keep | Words | Free-choice | Word-blocked | Δ | ±0.5 pp gate |
|---|---|---|---|---|---|
| 1.0 | 16 | 72.65% | 72.65% | +0.00 pp | PASS (sanity) |
| 0.5 | 8 | 72.65% | 71.73% | −0.92 pp | **FAIL** |
| 0.25 | 4 | 72.65% | 70.34% | −2.31 pp | **FAIL** |
| 0.125 | 2 | 72.65% | 66.14% | −6.51 pp | **FAIL** |

The earlier cached-cohort proxy predicted 0.00 pp at keep=0.25 and was wrong by 2.31 pp — the tell was
free-choice scoring *above* its own unpruned reference. No mask-selection decision gets made on that
proxy again.

**3. A baked gather is bit-exact, so no accuracy is lost at all.** Because popcount is invariant to bit
relabeling, hardwiring the Fisher-selected positions into the AM operand routing gives distances
identical to masked full-width classify. Verified over 20,000 windows at keep ∈ {0.125, 0.25, 0.5}:
**0 distance-vector mismatches, 0 prediction mismatches.** A synthesis-time permutation is pure wiring
(0 LUT), unlike the runtime-configurable gather that was rejected on cost.

This makes keep=0.125 reachable — a **2-word AM** (128 bits) carrying the accuracy of the full 16-word
design: 264 → 40 classify cycles (−85%), core latency 2.87 µs → 0.63 µs @ 100 MHz, and AM prototype
storage 8,192 → 1,024 FF.

## Scope limits

Findings 1 and 3 are exact (combinatorial / bit-exact identity). Finding 2 is a full-protocol HDC-2
measurement and is citable. `word_blocked_mask_eval.json` is the superseded cached-cohort proxy, kept
only to document why it misled; do not cite it. Area figures in the design doc remain estimates until
the per-module synthesis report lands in #29.
