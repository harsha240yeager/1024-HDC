# Reproducibility artifact — DATE submission

Everything needed to re-derive the manuscript's numbers, plus an explicit
account of what cannot be re-derived without a ZedBoard.

**Repository:** [harsha240yeager/1024-HDC](https://github.com/harsha240yeager/1024-HDC) ·
**Manuscript:** [harsha240yeager/Research-paper](https://github.com/harsha240yeager/Research-paper) ·
**Protocol:** HDC-2 · **Issue:** [#11](https://github.com/harsha240yeager/1024-HDC/issues/11)

---

## Start here

```bash
git clone https://github.com/harsha240yeager/1024-HDC.git
cd 1024-HDC
pip install -r python_ref/requirements.txt

# 1. Check every headline number against the committed evidence (seconds, no dataset needed)
python3 scripts/check_paper_numbers.py

# 2. Re-derive the Python results yourself (needs the dataset, see below)
bash scripts/reproduce_paper.sh --list          # what would run, with measured runtimes
bash scripts/reproduce_paper.sh --tier smoke    # ~30 min sanity pass
bash scripts/reproduce_paper.sh --tier core     # ~21 h, every S1-S5 claim
```

`check_paper_numbers.py` is the fastest way to audit the paper. It reads the
committed result files and compares 65 published values — accuracies, gaps,
confidence intervals, p-values, energies, latencies, window counts — against what
the manuscript prints, then exits non-zero if any of them drift:

```
65/65 claims verified
```

Reruns write to `results/repro/<tier>/` and never overwrite the committed
reference under `results/protocol_v2/`, so you can diff the two trees.

---

## What is and is not in this repository

| Included | Excluded, and why |
|----------|-------------------|
| Protocol HDC-2 split code, config, and leakage audit | `python_ref/HDC-EMG/dataset.mat` — Rahimi et al. release, GPLv3, not ours to redistribute |
| Fisher scoring, mask construction, all sweep runners | `python_ref/HDC-EMG/dataset_36.mat` — build it from raw UCI with `scripts/build_uci_emg_dataset.py` |
| Every result JSON/CSV behind every table and figure | Raw UCI tree (~252 MB) — download from UCI |
| SystemVerilog RTL, testbenches, nine co-simulation harnesses | Vivado project outputs (bitstream, checkpoints) — rebuild with `vivado_pack/` |
| Board replay logs, anchor replays, raw INA219 CSVs | — |
| ARM reference C source and build scripts | — |

### Getting the data

The five-subject board cohort uses the public HDC-EMG release:

```bash
git clone https://github.com/abbas-rahimi/HDC-EMG python_ref/HDC-EMG
```

The 36-subject cohort is built from the raw
[UCI EMG Data for Gestures](https://archive.ics.uci.edu/ml/datasets/emg+data+for+gestures)
corpus; `docs/TWIST2_36_REPRO.md` walks through it end to end.

---

## Environment

| Component | Version used |
|-----------|--------------|
| Python | 3.12 (3.10+ works); `numpy>=1.24`, `scipy>=1.10`, `matplotlib>=3.7` |
| OS | Ubuntu 22.04 for sweeps and board bring-up; Windows 11 + Git Bash also verified |
| FPGA toolchain | Vivado 2024.2, target `xc7z020clg484-1` (ZedBoard), PL @ 100 MHz |
| Board software | Vitis bare-metal, `board/HDC_DMA/` workspace |
| ARM baseline | `arm-none-eabi-gcc -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O2` (`scripts/build_arm_bench_cross.sh`) |
| Energy | TI INA219 (`0x40`, config `0x019F`) on ZedBoard J21, 10 mΩ shunt, logged from a Raspberry Pi |

`scripts/check_paper_numbers.py` is standard library only, so it runs in a bare
clone with nothing installed.

---

## Seeds and determinism

Every stochastic choice is fixed and recorded in the result JSON `meta` blocks.

| Seed | Value | Role |
|------|-------|------|
| Protocol shuffle | class index + 100 | Selects the TRAIN quarter within each class |
| Protocol global | 1 | Stride-1 window ordering |
| Item memory (deployed) | 42 | Item hypervectors in RTL and Python golden |
| Item memory (sensitivity) | 1, 7, 21, 42 | Section V-E |
| Random masks (iso-density) | 0–29 | 30 seeds per subject, iso-density table |
| Random masks (ranking, active-bit) | 0–4 | Sections V-D and IV-D |
| Silicon random mask | 0 | The only seed programmed on the board |
| Subject bootstrap | 0, 10,000 resamples | Iso-density confidence interval |

Reruns are bit-identical where the pipeline is deterministic: re-running the
split audit on a different OS reproduces `results/protocol_v2/split_audit.json`
byte for byte.

Two ablations subsample TEST to 15,000 windows per subject for tractability
(`max_test_windows_per_subject` in their `meta`): the ranking baselines and the
active-bit ablation. Everything else uses the full 493,512-window TEST split.
This is why the active support reads ~203–210 bits on the full split and
~202–209 on the subsampled runs; the paper quotes the full-split range.

---

## Claim-to-artifact map

`scripts/check_paper_numbers.py --markdown` prints this table with live values.
The experiment-level view:

| Paper element | Script | Committed evidence |
|---------------|--------|--------------------|
| Table I — Protocol HDC-2, overlap 0 | `scripts/audit_split_leakage.py` | `results/protocol_v2/split_audit.{json,csv}` |
| Table II — PL vs ARM baselines | `python_ref/run_arm_hdc_baseline.py`, board replay | `results/protocol_v2/arm_baseline/`, `results/phase3/energy_summary.txt` |
| Table III — silicon anchors A/B/C | `board/HDC_DMA/run_anchor_replay.sh ALL` | `results/protocol_v2/anchors/` |
| Table IV — iso-density ablation | `python_ref/run_twist1_sweep.py` + `tools/subject_level_stats.py` | `results/protocol_v2/twist1_keep0125_30seed/`, `results/phase3/twist1_silicon/` |
| Table VI — cross-subject pilot | `python_ref/run_twist2_sweep.py` | `results/protocol_v2/twist2_keep0125/` |
| Table VII — 36-subject keep grid | `scripts/run_twist2_36_v2_keep_grid.sh` | `results/protocol_v2/twist2_36_v2/keep_*/` |
| Table VIII — encoder ablation | `python_ref/run_encoder_ablation.py` | `results/protocol_v2/encoder_ablation/` |
| Sec. V-B — design-space sweep | `python_ref/run_hook_a_sweep.py` | `results/protocol_v2/hook_a/` |
| Sec. V-D — ranking baselines | `python_ref/run_ranking_baselines.py` | `results/protocol_v2/ranking_baselines/` |
| Sec. V-E — seed sensitivity | `python_ref/run_seed_sensitivity.py` | `results/seed_sensitivity/` |
| Sec. IV-C, VI — active support | `python_ref/run_active_bit_ablation.py` | `results/protocol_v2/active_bits/` |
| Figures | `python_ref/plot_results.py --paper` | `results/figures/` |

---

## Reproduction tiers

Runtimes are measured wall clock from the committed runs (`elapsed_s` in each
result JSON) on one 30-thread workstation.

| Tier | Wall clock | Covers |
|------|-----------|--------|
| `smoke` | ~30 min | Gate, split audit, quick iso-density and ranking passes |
| `core` | ~21 h | Every S1–S5 claim: baseline, 30-seed iso-density and statistics, ranking, active bits, seed sensitivity, encoder ablation, cross-subject pilot, figures |
| `full` | ~3 days | Adds the 35 h design-space sweep and the 36-subject keep grid |

```bash
bash scripts/reproduce_paper.sh --tier core            # everything in that tier
bash scripts/reproduce_paper.sh --only ranking         # one stage
bash scripts/reproduce_paper.sh --tier full --dry-run  # print commands only
```

Stages whose dataset is absent are skipped with the acquisition command printed,
so a partial clone still produces a useful run.

---

## Hardware-dependent results

These need the physical setup and cannot run from a clone. The logs they
produced are committed, so the numbers remain auditable.

| Result | Requires | Script |
|--------|----------|--------|
| Full-cohort replay of 493,512 windows | ZedBoard + JTAG | `board/HDC_DMA/run_phase3_emg.sh` |
| Anchors A/B/C at 72.78 / 72.78 / 72.84 % | ZedBoard, AXI mask reload only | `board/HDC_DMA/run_anchor_replay.sh ALL` |
| Silicon iso-density gap +10.33 pp (seed 0) | ZedBoard + mask patch | `board/HDC_DMA/run_twist1_board.sh --random-seeds 0` |
| J21 energy, 11.98 and 2088 µJ/window | INA219 on a Pi, 12 V sense at J21 | `scripts/run_energy_measure.sh`, then `scripts/aggregate_energy_runs.py` |
| Post-route utilization, 35,206 LUTs | Vivado 2024.2 | `vivado_pack/`, `scripts/dsweep_synth.tcl` |
| RTL co-simulation, nine harnesses | ModelSim/Questa | `vsim -c -do sim/run_core_cosim.do` |

Full energy procedure, including the batch-duration scaling that the paper's
equations describe: [`docs/ENERGY_METHODOLOGY.md`](ENERGY_METHODOLOGY.md).

---

## Provenance

| Item | Value |
|------|-------|
| RTL last modified | `aa65999` (2026-06-25) — unchanged by the HDC-2 protocol fix |
| Deployed bitstream | Phase 3 scatter-gather DMA design, `board/HDC_DMA/` |
| Export reference | Frozen `sw/emg_board_vectors_hdc2.h`, 493,512 windows, 72.78 % pooled |
| Board pass criterion | Every predicted label matches the golden model on the 200-vector batch (`sw/hdc_dma_stream_bench.c`), and full-cohort accuracy is within 0.5 pp of the export reference (`sw/hdc_emg_board_test.c`) |

---

## Known limitations of this artifact

- Silicon iso-density uses random-mask seed 0 only. Seeds 1–9 need JTAG mask
  reprogramming and are tracked in
  [#3](https://github.com/harsha240yeager/1024-HDC/issues/3); the paper labels
  the silicon figure a single-seed confirmation.
- The 36-subject cross-subject grid is Python only. No held-out-subject mask
  was programmed on the board.
- The 36-subject cohort uses a different preprocessing path from the
  five-subject board dataset, so absolute accuracies are not comparable across
  the two cohorts. Only within-cohort gaps are compared.
- Energy is whole-board at J21. Isolating the PL rail would need a board
  modification and is listed as future work.
- Per-window label equality against the export reference is enforced on the
  200-vector golden batch, not on all 493,512 replayed windows: the replay
  firmware scores against ground truth and gates on cohort accuracy. Anchor C
  therefore sits 0.01 pp from its export reference, well inside the 0.5 pp gate.

---

## License and citation

RTL, Python, scripts, and documentation in this repository are original work.
The EMG dataset and its reference encoder (Rahimi et al.) are GPLv3 and must be
fetched separately; they are not redistributed here. Cite the dataset alongside
this artifact when reusing the EMG results.
