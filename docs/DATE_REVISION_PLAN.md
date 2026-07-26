# DATE 2027 — Major Revision Plan

**Trigger:** Weak-reject review (2/5) — protocol leakage, weak cross-subject test, under-sampled random baselines, claim/implementation mismatch.

**Repos:**
- Experiments + RTL: [1024-HDC](https://github.com/harsha240yeager/1024-HDC) (this repo)
- Manuscript: [Research-paper](https://github.com/harsha240yeager/Research-paper)

**Rule:** Do not update paper headline numbers until **Phase 1** reruns complete under **Protocol HDC-2**.

**GitHub tracking:** [1024-HDC issues #1–#11](https://github.com/harsha240yeager/1024-HDC/issues) (experiments) · [Research-paper issues #1–#4](https://github.com/harsha240yeager/Research-paper/issues) (manuscript)

---

## Dependency graph

```
Phase 1 (disjoint split) ──► Phase 2 (cross-subject stress)
         │                            │
         ├─► Phase 3 (random baselines + stats)
         ├─► Phase 4 (item-memory seeds)
         ├─► Phase 5 (257-bit + ranking baselines)
         ├─► Phase 6 (encoder ablation)
         ├─► Phase 7 (energy methodology)
         │
         └─► Phase 8–13 (paper + reproducibility) after Phases 1–5 numbers exist
```

---

## Phase 1 — Fix train/test protocol (BLOCKER)

**Issue:** [#1](https://github.com/harsha240yeager/1024-HDC/issues/1)

Current `split_train_test()` returns the **full recording** as test while training uses the first 25% of each class → train windows appear in test (stride-1 overlap amplifies leakage).

### Protocol HDC-2 specification

| Item | Rule |
|------|------|
| Train | First 25% of each class per subject (shuffle seed+100 within class, unchanged) |
| Test | Remaining 75% of each class — **strictly disjoint indices** |
| Boundary | Drop ±1 window at train/test boundary (optional but recommended) |
| Prototypes | Built from TRAIN encodings only |
| Fisher scores | Computed from TRAIN encodings only |
| Normalization / quantization | Fit on train statistics only (audit current pipeline) |
| Reporting | Per-subject train window count, test window count, overlap (=0) |

### Implementation checklist

- [ ] Add `python_ref/config/emg_baseline_v2.json` (Protocol HDC-2)
- [ ] Rewrite `split_train_test()` in `scripts/export_emg_board_vectors.py`
- [ ] Add `scripts/audit_split_leakage.py` (overlap count, per-subject table)
- [ ] Propagate split to: `run_twist1_sweep.py`, `run_hook_a_sweep.py`, `run_twist2_sweep.py`, `patch_emg_anchor.py`, `export_fisher_pooled.py`, `baseline_common.py`, `run_arm_hdc_baseline.py`, `run_emg_baseline.py`
- [ ] Unit test: `assert train_idx ∩ test_idx == ∅`

### Full rerun (all headline results invalidate)

```bash
python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline_v2.json

python python_ref/run_emg_baseline.py --config emg_baseline_v2.json
python scripts/export_emg_board_vectors.py --config emg_baseline_v2.json
python scripts/regenerate_emg_protos.py --config emg_baseline_v2.json
python scripts/export_fisher_pooled.py --config emg_baseline_v2.json

# Board (ZedBoard)
bash board/HDC_DMA/run_phase3_emg_replay.sh
bash board/HDC_DMA/run_anchor_replay.sh A
bash board/HDC_DMA/run_anchor_replay.sh B
bash board/HDC_DMA/run_anchor_replay.sh C
python python_ref/run_arm_hdc_baseline.py --config emg_baseline_v2.json

python python_ref/run_hook_a_sweep.py --config emg_baseline_v2.json
python python_ref/run_twist1_sweep.py --config emg_baseline_v2.json
python python_ref/run_twist2_sweep.py --config emg_baseline_v2.json
```

### Deliverables

- [ ] `results/protocol_v2/split_audit.json` + per-subject CSV
- [ ] Updated board export + golden reference under HDC-2
- [ ] New silicon replay log (report new N_test, not 658k until verified)
- [ ] Paper Table: Protocol HDC-2 replaces HDC-1

**Gate:** Overlap = 0 for all subjects before any other phase starts.

---

## Phase 2 — Cross-subject transfer under accuracy stress

**Issue:** [#2](https://github.com/harsha240yeager/1024-HDC/issues/2)

**Depends on:** Phase 1

Current Twist 2 is tautological (identical masks @128 bits; lossless @512 bits).

### Experiment design

**Cohort:** S1–S36, same preprocessing path as silicon where possible (`dataset.mat` export path preferred over `dataset_36.mat` if feasible).

**Train mask on:** S1–S18 TRAIN partitions only  
**Evaluate on:** S19–S36 TEST partitions only (disjoint split per subject)

**Keep ratios (bits @ D=1024):** 32, 64, 96, 128, 192, 256  
(keep_ratio = bits/1024)

**Three mask types on held-out subjects:**

| Mask | Trained on |
|------|------------|
| Random | No labels — uniform over active support (see Phase 5) |
| Pooled Fisher | S1–S18 TRAIN only |
| Local oracle | Each held-out subject's own TRAIN partition |

**Success criterion:** At least one keep ratio where:
- pooled ≠ local mask (report Jaccard),
- pruning causes measurable loss vs full-width,
- pooled retains most of local-oracle benefit (e.g. ≥80% of local gap closed).

### Implementation checklist

- [ ] Extend `run_twist2_sweep.py` with keep grid `{32,64,96,128,192,256}` bits
- [ ] Add `--mask-type {random,pooled,local}` and `--random-support active|full`
- [ ] Output per-subject accuracy + mask Jaccard + gap tables
- [ ] Plot: keep ratio vs pooled/local/random mean accuracy (36 subjects)

### Deliverables

- [ ] `results/twist2_v2/` with JSON + CSV + figure
- [ ] Paper claim: *"On unseen subjects, pooled Fisher masks retain most of the local-oracle benefit under accuracy-stressing compression."*

---

## Phase 3 — Expand random-mask baseline + statistics

**Issue:** [#3](https://github.com/harsha240yeager/1024-HDC/issues/3)

**Depends on:** Phase 1

### Sample sizes

| Platform | Random masks | Seeds |
|----------|--------------|-------|
| Python | 20–30 per keep ratio | 0–29 |
| FPGA | ≥5 per keep ratio | reprogram mask via AXI only |

### Statistics (subject-level, not window-level)

- [x] Paired per-subject gaps (Fisher − random)
- [x] Mean, median, std across subjects
- [x] 95% CI (bootstrap over **subjects**)
- [x] Wilcoxon signed-rank or paired t-test (report p-value)
- [x] Never treat windows as i.i.d. samples

### Result table template

| Keep bits | Fisher mean | Random mean | Gap | 95% CI | p-value |
|-----------|-------------|-------------|-----|--------|---------|
| 64 | | | | | |
| 128 | | | | | |
| 256 | | | | | |

### Implementation checklist

- [x] Add `python_ref/tools/subject_level_stats.py`
- [x] Extend `run_twist1_sweep.py` for 30 seeds (`protocol_v2/twist1_keep0125_30seed/`)
- [ ] FPGA: ≥5 silicon random seeds (deferred — JTAG; seed 0 done)
- [x] Summarize in `results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.*`

---

## Phase 4 — Item-memory seed sensitivity

**Issue:** [#4](https://github.com/harsha240yeager/1024-HDC/issues/4)

**Depends on:** Phase 1

**Seeds:** `{1, 7, 21, 42}` (minimum)

Per seed report:
- [ ] Full-width accuracy (Python + silicon if time)
- [ ] Number of varying bit positions (active support)
- [ ] Fisher vs random gap @ 128 bits
- [ ] Retained-bit accuracy curve

### Implementation

- [ ] Parameterize `item_mem_seed` in sweep configs
- [ ] Script: `python_ref/run_seed_sensitivity.py --seeds 1,7,21,42`
- [ ] Output: `results/seed_sensitivity/`

---

## Phase 5 — Active-bit ablation (257 positions) + ranking baselines

**Issue:** [#5](https://github.com/harsha240yeager/1024-HDC/issues/5) (257-bit) · [#9](https://github.com/harsha240yeager/1024-HDC/issues/9) (baselines)

**Depends on:** Phase 1

### 5a — Why only ~203–210 bits vary? (HDC-2; legacy note said ~257)

- [x] Add `active_bit_support()` / `active_bit_mask()` / `mask_random_from_support()` in `hdc_ref.py`
- [x] Report active count across: subjects, item-memory seeds, D sweep (`python_ref/run_active_bit_ablation.py` → `results/protocol_v2/active_bits/`)
- [x] Diagnose: continuous value flip budget (`D/n_levels`), 20-bind bundling, majority collapse vs single-record support
- [x] Explain why keep=512 is lossless (512 > active support)
- [x] **Fair random baseline:** sample only from active support, not all 1024 bits

### 5b — Ranking baselines (128-bit accuracy)

| Method | Ranking cost | Retraining |
|--------|--------------|------------|
| Random (full 1024) | low | no |
| Random (active support) | low | no |
| Variance | low | no |
| Mutual information | medium | no |
| Class-mean separation | low | no |
| Prototype disagreement freq. | low | no |
| Per-bit entropy | low | no |
| Fisher (current) | low | no |
| Learned mask (optional) | high | yes |

- [x] Implement baselines in `hdc_ref.py` + `run_ranking_baselines.py`
- [x] Table: Method × 128-bit accuracy × ranking cost → `results/protocol_v2/ranking_baselines/`

---

## Phase 6 — Encoder gap: 74% vs 90%

**Issue:** [#6](https://github.com/harsha240yeager/1024-HDC/issues/6)

**Choose one path:**

### Path A (stronger paper): BSC encoder in hardware

- [ ] Implement or approximate Stage-B BSC bind-record encoder in PL
- [ ] Re-run pruning study on stronger baseline

### Path B (acceptable): Controlled ablation table — DONE

| Configuration | Spatial mean (HDC-2 / noted) |
|---------------|------------------------------|
| Literature BSC (full test) | 90.17% |
| Stage B @ HDC-2 | 89.37% |
| + item-mem seed 42 | 90.82% |
| + 16-level CiM | 90.26% |
| RTL item mem + 4 binds | 73.28% (−17.0 pp) |
| RTL 20 binds (deployed) | 72.89% (−0.4 pp) |

- [x] Script: `python_ref/run_encoder_ablation.py`
- [x] Results: `results/protocol_v2/encoder_ablation/`
- [x] Paper table `tab:encoder` (Path B; no BSC in PL)

---

## Phase 7 — Align claims with what pruning changes

**Issue:** [#7](https://github.com/harsha240yeager/1024-HDC/issues/7)

**Current fact:** Runtime mask does not reduce LUT count or whole-board J21 energy.

### Path A — Compact datapath (hardware savings)

- [ ] RTL: compact retained-bit XOR/popcount (128/512/1024 variants)
- [ ] Re-synthesize; report LUT/FF/timing/dynamic power
- [ ] Compare energy per window vs full-width RTL

### Path B — Honest reframe (recommended if no RTL change)

Paper contribution becomes:
> Runtime-selectable, accuracy-preserving bit-position compression on a fixed-width FPGA datapath.

- [ ] Remove "energy-saving pruning" language
- [ ] PL vs ARM energy = platform comparison only
- [ ] Pruning benefit = accuracy under iso-density + effective Hamming width (logical)

**Paper issue:** [#12](https://github.com/harsha240yeager/Research-paper/issues/1) (claim alignment)

---

## Phase 8 — Energy methodology

**Issue:** [#8](https://github.com/harsha240yeager/1024-HDC/issues/8)

Document from existing `scripts/ina219_log.py` + `results/phase3/energy_runs/`:

- [ ] INA219 model, shunt value, calibration formula
- [ ] Config register `0x019F` → sampling rate, conversion time, averaging
- [ ] Idle power measurement procedure (duration, n runs)
- [ ] Batch integration: batch size, repetitions (target n≥10), CI
- [ ] Formula: E_dynamic = (P_active − P_idle) × t
- [ ] Boundaries: includes PS+PL+DDR+DMA setup; ARM compiler flags, CPU freq
- [ ] Representative power trace figure (static vs batch)
- [ ] Clarify 175× = latency × static-dominated board power

Deliverable: `docs/ENERGY_METHODOLOGY.md` + half-page in paper appendix.

---

## Phase 9 — Fix internal inconsistencies — DONE

**Issue:** [#10](https://github.com/harsha240yeager/1024-HDC/issues/10) (hardware fig) · Research-paper [#2](https://github.com/harsha240yeager/Research-paper/issues/2)

- [x] Fig. 1: **5-class argmin** — `Research-paper/figures/final_arch1.*`
- [x] Five prototypes vs eight AM slots — explained in manuscript §Architecture
- [x] Spatial mean vs pooled window — defined in protocol table
- [x] Bit-exact: every predicted label matched frozen reference over all N windows
- [x] Latency: Phase 3 mean ~4 µs (range 4–7)
- [x] 200× / 175×: calculations in `tab:baselines` caption
- [x] Anchor C +0.07 pp vs A explained (active-support mask; bit-exact)

---

## Phase 10 — Reproducibility artifact — DONE

**Issue:** [#11](https://github.com/harsha240yeager/1024-HDC/issues/11)

Released as a tagged GitHub release plus [`docs/REPRODUCIBILITY.md`](REPRODUCIBILITY.md):

- [x] Split-generation code + Protocol HDC-2 config (`audit_split_leakage.py`, `emg_baseline_v2.json`)
- [x] All random seeds documented — seed table in `REPRODUCIBILITY.md`
- [x] Fisher mask generation scripts (`hdc_ref.py`, `export_fisher_pooled.py`)
- [x] Exported prototypes + test vectors (HDC-2) — frozen export reference, 493,512 windows
- [x] RTL commit hash (`aa65999`) + Vivado 2024.2 + `vivado_pack/` + `dsweep_synth.tcl`
- [x] ARM reference (`libhdc_arm_ref`) + compiler flags (`-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O0 -g`)
- [x] Board replay scripts + INA219 logs (raw CSV under `results/phase3/energy_runs/`)
- [x] One-command: `scripts/reproduce_paper.sh` — tiers `smoke` (~30 min) / `core` (~21 h) / `full` (~3 days)
- [x] **`scripts/check_paper_numbers.py`** — re-derives all 49 published numbers from committed
      artifacts, stdlib only, exits non-zero on drift (currently 49/49 PASS)

Two inconsistencies the checker caught and fixed: anchor C board accuracy
(72.85 → 72.84 %, the 72.85 % is the export reference) and the active-support
range quoted two ways (now 203–210 everywhere, from the full-split runs).

Paper: reproducibility statement with URL + license in §IV-D.

---

## Phase 11 — Rewrite title and abstract — DONE

**Issue:** Research-paper [#3](https://github.com/harsha240yeager/Research-paper/issues/3)

**Chosen title:** *Bit-Position Pruning for Hyperdimensional Computing on FPGA: Support, Not Score*

Shortened from the working version *…: Informed Selection Is Active-Support Identification*, and "FPGA Hyperdimensional Computing" reordered to "Hyperdimensional Computing on FPGA" so the adjective sits with the noun it belongs to.

Superseded the original *Fisher-Guided Bit Selection for a Bit-Exact Streaming HDC Accelerator on Zynq* once the ranking sweep showed six criteria are interchangeable, which makes a Fisher-specific title unsupportable.

Abstract: problem → method → +6.90 pp subject-level (CI) → support-not-ranking explanation → 72.78% replay + PL/ARM → fixed-width energy limitation.

---

## Phase 12 — Reorganize paper around one claim — DONE

**Issue:** Research-paper [#4](https://github.com/harsha240yeager/Research-paper/issues/4)

Claim: runtime Fisher bit-position selection on a bit-exact fixed-width streaming HDC datapath.

- [x] 3 contributions (silicon+cost, iso-density, cross-subject protocol check)
- [x] §Experimental Protocol and Methodology (HDC-2)
- [x] Demoted MLP to optional context; cut legacy HDC-1 Twist 2 tautology line
- [x] Conclusion aligned with Path B (accuracy under iso-density; no board-joule claim)

---

## Suggested timeline

| Week | Focus |
|------|-------|
| 1 | Phase 1 — implement HDC-2, audit, rerun Python |
| 2 | Phase 1 — board replay + Phase 3 random baselines start |
| 3 | Phase 2 cross-subject + Phase 4 seeds + Phase 5 active-bit |
| 4 | Phase 6 encoder ablation + Phase 8 energy doc |
| 5 | Phases 9–12 paper rewrite + Phase 10 artifact |

---

## Status board (update as you go)

| Phase | Status | Blocker |
|-------|--------|---------|
| 1 Protocol HDC-2 | ⏳ In progress — split fix + CI gate | — |
| 2 Cross-subject stress | ⏳ Blocked | Phase 1 |
| 3 Random + stats | ⏳ Blocked | Phase 1 |
| 4 Seed sensitivity | ⏳ Blocked | Phase 1 |
| 5 Active-bit + baselines | ⏳ Blocked | Phase 1 |
| 6 Encoder ablation | ⏳ Not started | — |
| 7 Claim alignment | ⏳ Not started | Phase 7 path choice |
| 8 Energy methodology | ⏳ Not started | — |
| 9 Inconsistencies | ⏳ Not started | — |
| 10 Reproducibility | ✅ Done — artifact + 49/49 claim check | — |
| 11 Title/abstract | ✅ Done | Research-paper #3 |
| 12 Paper reorg | ⏳ Blocked | New results |
