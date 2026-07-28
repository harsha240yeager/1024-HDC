# Split-paper plan — hardware vs iso-density science

Companion to the combined DATE manuscript (`Research-paper/conference_101719.tex`).
Use this **only after** a split decision — not as a reason to delay the current
submission unless you commit to the experiments below.

**Rule:** two strong papers need **two headline results**. Splitting the existing
text alone yields overlapping borderline submissions. Each paper must add at
least one experiment the combined paper does not have.

---

## 1. The two papers at a glance

| | **Paper 1 — Hardware** | **Paper 2 — Science** |
|--|--------------------------|------------------------|
| **Working title** | Runtime-programmable bit-masks on a verified streaming HDC accelerator (Zynq) | Iso-density bit-position selection in HDC: active support, not ranking score |
| **One-line pitch** | Bit-exact 1024-bit HDC on Zynq with full-cohort silicon replay; runtime mask load without resynthesis; **narrow or gated datapath shows measurable LUT/energy/latency vs keep ratio** | At fixed K of D bits, which positions matter; mechanism is active support; six criteria tie under sparse support; **Stage-B tests when criteria separate** |
| **Hero metric** | Δ LUT / Δ µJ / Δ µs vs keep at fixed accuracy | Δ accuracy (pp) informed vs random-all vs random-support at fixed K |
| **Silicon role** | **Central** | Optional appendix (1–3 seeds) |
| **Primary venue** | DATE, FPL, CASES → journal: TVLSI / TCAS-II | TBioCAS, TNNLS (letters), NCE → journal: longer HDC/ML |
| **Novelty target** | ~7.5 | ~7.0–8.0 (if dense-support experiment separates criteria) |
| **Reuse from combined** | ~70% of Sec. III–IV, V-A, V-B, hardware limits | ~80% of protocol, V-D–V-F, ranking, cross-subject |

---

## 2. Paper 1 — section outline (hardware)

Target length: **6–8 pages** conference; **10–12** journal extension.

### Suggested sections

1. **Introduction**
   - Problem: verified edge HDC needs system-level evidence (DMA, mask programming, energy honesty).
   - Gap: prior FPGA HDC lacks runtime keep-ratio change without resynthesis + same-board software baseline.
   - Contributions (3 bullets): bit-exact accelerator + full-cohort replay; runtime AXI4-Lite masks; **physical savings on narrow/gated implementation** (not logical mask only).

2. **Background** (short)
   - HDC inference = encode + masked Hamming argmin (one equation).
   - Related FPGA HDC (Schmuck, SparseHD, Antonio) — **Table from combined paper**, no iso-density story.

3. **Architecture** (from combined Sec. III)
   - Figure: PS–PL dataflow (`final_arch1.pdf`).
   - Encoder + `popcount_am` + mask path.
   - **New subsection:** narrow 128-bit compare **or** clock-gated popcount lanes — block diagram delta vs baseline.

4. **Implementation**
   - Zynq-7020, 100 MHz, scatter-gather DMA.
   - Phase 1/2/3 latency table (3 / 7.5 / 4.6 µs).
   - Post-route: LUT/FF/slice; **compare baseline vs narrow/gated at each keep anchor**.

5. **Verification**
   - Nine co-sim harnesses; 200-vector golden batch; 493k-window replay (Δ0 pp).
   - **Scope claim:** bit-exact per window on golden batch + cohort accuracy gate (not all-window label dump).

6. **Evaluation**
   - Anchors A/B/C accuracy + energy lower bounds (flat on baseline RTL — motivates new RTL).
   - ARM `-O2` baseline; optional NEON follow-up.
   - **Main result figure:** keep ratio vs LUT / vs µJ (l.b.) / vs µs — **separation only on new RTL**.
   - Multi-seed silicon random masks (seeds 0–9) at keep = 0.125 — distribution, not one point.

7. **Discussion**
   - Fixed-width XOR-then-mask = null hardware benefit (honest baseline).
   - Narrow/gated design = when mask **does** buy hardware.
   - Energy methodology (idle-calibrated l.b.) — brief, cite companion paper for mask *selection* science.

8. **Conclusion**
   - Verified platform + runtime reconfigurability + **measured** compression benefit on redesigned datapath.

9. **Acknowledgment** — AI disclosure if venue requires; no overlap with Paper 2 funding text until camera-ready.

### Remove from Paper 1 (move to Paper 2 or cite)

- Fisher equation and mask construction detail (one sentence + cite Paper 2).
- Six ranking criteria, Jaccard, support-restricted random (−1.13 pp).
- Cross-subject 36-subject grid.
- “Support, not score” as **main** finding — at most one paragraph motivation for why masks differ.

---

## 3. Paper 2 — section outline (science)

Target length: **8–10 pages** journal; **6 pages** workshop if shortened.

### Suggested sections

1. **Introduction**
   - Question: when exactly K of D hypervector bits are kept, does **which** K change predictions?
   - Gap: pruning literature changes sparsity level or retrains; rarely fixes K (iso-density).
   - Contributions: HDC-2 protocol; iso-density effect (+6.9 pp); mechanism (active support ~203–210); six criteria tie; cross-subject bounds; **Stage-B dense-support falsification**.

2. **Protocol HDC-2** (from combined Table + Sec. IV-A)
   - Disjoint split, metrics (spatial vs pooled), pre-specified targets.
   - **Prominent box:** active support, iso-density, spatial vs pooled — one-line definitions.

3. **Encoder and datasets**
   - RTL encoder (~73% pooled) — **primary** for silicon-linked claims.
   - Stage-B BSC (~90%) — literature reference + **Paper 2 extension experiments**.
   - Clarify envelope 0–21 → 16-level value table; document export grid (`level21_to_grid`).

4. **Mask construction**
   - Fisher-style score (Eq. 2); per-subject vs pooled masks.
   - Random baselines: all positions / active-support-only / 30 seeds.

5. **Results — iso-density** (from V-D, twist1)
   - Main figure: informed vs random-all vs random-support at keep = 0.125.
   - Statistics: subject bootstrap CI, Wilcoxon, paired t-test.
   - Silicon: one seed (+10.33 pp) as **confirmation only** — or drop to appendix.

6. **Results — ranking baselines** (Sec. V-D)
   - Five distinct criteria; identical predictions; Jaccard table.
   - Active support measurement (203–210; value-table ceiling 327).

7. **Results — cross-subject** (V-F, twist2)
   - S1–S5 pilot + 36-subject keep grid as **primary** generalization evidence.

8. **Results — dense-support extension** (**NEW — required for strong Paper 2**)
   - Stage-B iso-density at keep ∈ {0.125, 0.25, 0.5}.
   - Report: do criteria still tie? does support-restricted random still close the gap?

9. **Discussion**
   - Support, not score; encoder dependence; redundant feature axis limitation.
   - What would falsify the claim; link to Paper 1 for “same masks on silicon.”

10. **Conclusion**

### Remove from Paper 2 (move to Paper 1 or cite)

- Full DMA phase table, slice occupancy, INA219 setup (cite Paper 1).
- Prior-FPGA throughput table as main contribution.
- 175× latency as headline — optional one sentence “validated on companion platform.”

---

## 4. Experiments — scripts, artifacts, gates

### Paper 1 experiments (hardware)

| ID | Experiment | Script / path | Output | Gate / “done” |
|----|------------|---------------|--------|----------------|
| **H1** | **Narrow or gated `popcount_am`** | RTL: `rtl/popcount_am.sv`, `rtl/pruning_mask.sv`; synth via Vivado flow in `board/HDC_DMA/` | Post-route LUT/FF vs keep; anchor accuracy A/B/C | **Required.** ≥10% LUT or measurable µJ drop at keep=0.125 vs full-width baseline, accuracy within 0.5 pp |
| **H2** | Multi-seed silicon iso-density | `scripts/run_golden_jtag.py`, `scripts/run_golden_jtag.tcl`; board replay firmware | `results/protocol_v2/twist1_silicon/random_seed_*/` | ≥5 seeds; report mean ± std of informed−random gap |
| **H3** | Seeds 1–9 mask reprogram | JTAG + `sw/emg_board_vectors_hdc2.h` export variants | Per-seed `board_emg_replay.txt` | Issue #3 closure |
| **H4** | Anchor energy (unchanged) | `scripts/run_energy_one_run.sh`, `results/phase3/energy_summary.txt` | Already committed | Reuse; label l.b. |
| **H5** | ARM NEON baseline (optional) | Extend `python_ref/run_arm_hdc_baseline.py`, `sw/libhdc_arm_ref` | `results/baselines/arm_hdc_results.json` | ≥10% ARM speedup vs current `-O2` |
| **H6** | Full-cohort replay (unchanged) | Board test `sw/hdc_emg_board_test.c` | `results/protocol_v2/anchors/` | Already Δ0 pp — reuse |

**Suggested new script (to add):**

```bash
# scripts/run_silicon_random_seeds.sh  — loop seeds 0..9, program mask, replay, log
# scripts/compare_narrow_vs_baseline_lut.sh  — parse util reports into one CSV
```

### Paper 2 experiments (science)

| ID | Experiment | Script / path | Output | Gate / “done” |
|----|------------|---------------|--------|----------------|
| **S1** | **Stage-B iso-density** | `python_ref/repro/stage_b_bsc.py` + **new** `python_ref/run_twist1_stage_b.py` (wrap twist1 logic with Stage-B encoder) | `results/protocol_v2/twist1_stage_b/` | **Required.** Informed vs random-all vs random-support at keep=0.125; report whether gap shrinks or criteria separate |
| **S2** | RTL iso-density (existing) | `python_ref/run_twist1_sweep.py` | `results/twist1/`, `results/protocol_v2/` | Reuse |
| **S3** | Ranking baselines | `python_ref/run_ranking_baselines.py` | `results/protocol_v2/ranking_baselines/` | Reuse |
| **S4** | Active support / seeds | `python_ref/run_seed_sensitivity.py` | `results/seed_sensitivity/` | Reuse; add value-table ceiling (327) in text |
| **S5** | Cross-subject 36 | `python_ref/run_twist2_sweep.py` (+ `run_twist2_36_v2_keep_grid.sh`) | `results/protocol_v2/twist2_36_v2/` | Reuse; elevate to main body |
| **S6** | Fair random baselines figure | `python_ref/plot_results.py` | `results/figures/twist1_informed_vs_random_keep0125.pdf` | Extend with 3-bar panel |
| **S7** | Encoder ablation (4 vs 20 binds) | `python_ref/run_encoder_ablation.py` | `results/protocol_v2/encoder_ablation/` | Document redundant feature axis |
| **S8** | Dense encoder + real features (optional) | Modify `export_emg_board_vectors.py` / encoder config | New export + Python only | Raises ~73% ceiling; optional for Paper 2 v2 |

**Suggested new script:**

```bash
python python_ref/run_twist1_stage_b.py --keep 0.125 --seeds 30 --out results/protocol_v2/twist1_stage_b/
```

Implement by copying `run_twist1_sweep.py` and swapping `HDCEngine` for Stage-B encode path from `repro/stage_b_bsc.py`.

---

## 5. Overlap and citation map

When both exist, **cross-cite once** in intro/implementation; do **not** duplicate full sections.

```
┌─────────────────────────────────────────────────────────────────┐
│                     SHARED FOUNDATION (cite, don't repeat)       │
│  HDC-2 protocol · UCI EMG · D=1024 · item-mem seed 42         │
│  Fisher mask definition (Paper 2 owns; Paper 1 cites Eq. in P2) │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────────┐          ┌──────────────────────┐
│ PAPER 1 (Hardware)   │          │ PAPER 2 (Science)    │
│ Owns:                │          │ Owns:                │
│ · RTL + verification │◄─ cite ──│ · Iso-density stats  │
│ · DMA latency table  │── cite ─►│ · Ranking tie        │
│ · LUT/energy vs keep │          │ · Cross-subject grid │
│   (narrow/gated RTL) │          │ · Active support mech│
│ · Multi-seed silicon │          │ · Stage-B extension  │
└──────────────────────┘          └──────────────────────┘
```

### Citation wording (templates)

**In Paper 1:**

> Mask positions are ranked on TRAIN queries using the iso-density protocol of [Paper 2, Eq. (2)]; here we evaluate only whether those masks can be loaded at runtime and whether a **physical** datapath exploits reduced keep ratio.

**In Paper 2:**

> Masks were validated on a bit-exact Zynq implementation [Paper 1] for the S1–S5 cohort (optional: one-seed iso-density confirmation in appendix).

### Overlap budget (reviewer-facing)

| Content | Paper 1 | Paper 2 | Rule |
|---------|---------|---------|------|
| HDC-2 protocol table | Summary ½ page | Full | P2 is canonical |
| Architecture figure | Full | Omit or small inset | P1 only |
| Iso-density +6.9 pp | 1 paragraph + cite | Full section | P2 only |
| 493k replay | Full | 1 sentence | P1 only |
| Energy Eq. (idle l.b.) | Full | Omit | P1 only |
| Six criteria tie | Omit | Full | P2 only |
| Prior-FPGA table | Full | Related work ½ page | P1 primary |
| Stage-B ~90% | 1 sentence | Full ablation | P2 only |

**Target:** ≤15% verbatim overlap; shared protocol described once in Paper 2, cited in Paper 1.

---

## 6. Phased execution plan

### Phase 0 — Now (combined submission)

- Submit **one** VLSID/DATE paper if deadline applies.
- Do **not** split prose yet.

### Phase 1 — Paper 2 prep (2–3 weeks, Python only)

1. Implement `run_twist1_stage_b.py` (S1).
2. Regenerate three-baseline figure (S6).
3. Draft Paper 2 intro + results from existing artifacts.
4. **Decision point:** If Stage-B **separates** criteria → prioritize Paper 2 journal. If still ties → Paper 2 is “universal support effect” (weaker but complete).

### Phase 2 — Paper 1 prep (1–2 months, RTL + lab)

1. Design narrow/gated `popcount_am` (H1).
2. Re-verify co-sim + 200 golden + anchors A/B/C.
3. Run seeds 1–9 (H2/H3).
4. Draft Paper 1 with **Pareto figure** keep vs LUT/µJ.

### Phase 3 — Submission order

| Order | Paper | When |
|-------|-------|------|
| 1 | Combined (if not yet submitted) | Now |
| 2 | Paper 2 journal | After S1 results |
| 3 | Paper 1 conference | After H1 + H2 |

If combined is **accepted**: Paper 2 = journal extension of science; Paper 1 = short hardware note or conference v2 with H1.

If combined is **rejected** (“incremental” / “no hardware win”): lead with Paper 1 after H1, Paper 2 in parallel.

---

## 7. Success criteria (“strong” split)

### Paper 1 is strong when a reviewer can write:

> Verified full-cohort HDC on Zynq with runtime mask programming; a **narrow/gated** implementation reduces **LUT by X%** and/or **board-energy lower bound by Y%** at keep = 0.125 while holding **72.8%** accuracy; multi-seed silicon confirms mask programming stability.

**Without H1:** stays borderline — same as today.

### Paper 2 is strong when a reviewer can write:

> First iso-density study fixing K while varying position choice, with **active-support mechanism** quantified; six standard rankings are interchangeable under sparse RTL support; on **dense Stage-B encoder**, criterion quality **[does / does not]** separate — establishing when bit-position discriminability matters.

**Without S1:** publishable workshop/journal short, novelty ~6.5 — better than split-as-is, not a strong split.

---

## 8. File checklist when splitting repos / Overleaf

| Item | Paper 1 project | Paper 2 project |
|------|-----------------|-----------------|
| Main `.tex` | `hardware_zynq_hdc.tex` | `isodensity_hdc_bits.tex` |
| Figures | arch, baselines, pareto LUT/energy, prior table | twist1, ranking, cross-subject 36, Stage-B panel |
| Bib | shared `refs.bib` subset | shared + more ML/HDC pruning |
| Artifact | bitstream + replay logs + util reports | `results/protocol_v2/*`, seed sensitivity JSON |
| Claim checker | New `check_paper1_numbers.py` | Extend `check_paper_numbers.py` for Paper 2 claims |

---

## 9. Quick decision matrix

| You can invest… | Best action |
|-----------------|-------------|
| Nothing before deadline | **One combined paper** |
| 2–3 weeks Python | Start **Paper 2** draft; keep combined submitted |
| 1–2 months RTL + lab | **Split** after H1 + S1 |
| RTL only, no Stage-B | **Paper 1 only** — don’t split |
| Stage-B only, no RTL | **Paper 2 only** — don’t split |

---

## 10. GitHub experiment tracker (DATE 2027 strong accept)

**Epic:** [#20](https://github.com/harsha240yeager/1024-HDC/issues/20) · **Plan doc:** `docs/DATE2027_ISSUES.md`

| Order | Issue | Priority | Paper |
|------:|-------|----------|-------|
| 1 | [#21](https://github.com/harsha240yeager/1024-HDC/issues/21) Stage-B iso-density (S1) | P0 | 2 |
| 2 | [#22](https://github.com/harsha240yeager/1024-HDC/issues/22) Stage-B ranking baselines | P0 | 2 |
| 3 | [#23](https://github.com/harsha240yeager/1024-HDC/issues/23) Three-baseline figure | P1 | 2 |
| 4 | [#24](https://github.com/harsha240yeager/1024-HDC/issues/24) Active-support mechanism | P1 | 2 |
| 5 | [#25](https://github.com/harsha240yeager/1024-HDC/issues/25) Encoder redundancy | P1 | 2 |
| 6 | [#26](https://github.com/harsha240yeager/1024-HDC/issues/26) Silicon seeds 1–9 | P0 | Both |
| 7 | [#27](https://github.com/harsha240yeager/1024-HDC/issues/27) Silicon seed script | P1 | Both |
| 8 | [#28](https://github.com/harsha240yeager/1024-HDC/issues/28) Design narrow/gated RTL | P0 | 1 |
| 9 | [#29](https://github.com/harsha240yeager/1024-HDC/issues/29) Implement + synth | P0 | 1 |
| 10 | [#30](https://github.com/harsha240yeager/1024-HDC/issues/30) Co-sim + golden | P1 | 1 |
| 11 | [#31](https://github.com/harsha240yeager/1024-HDC/issues/31) Board LUT/energy/latency | P1 | 1 |
| 12 | [#32](https://github.com/harsha240yeager/1024-HDC/issues/32) Pareto figure | P2 | 1 |
| 13 | [#36](https://github.com/harsha240yeager/1024-HDC/issues/36) Integrate manuscript | P1 | Both |
| 14 | [#37](https://github.com/harsha240yeager/1024-HDC/issues/37) Claim checker + figures | P1 | Both |
| 15 | [#38](https://github.com/harsha240yeager/1024-HDC/issues/38) DATE submit checklist | P1 | Both |

Optional P2: [#33](https://github.com/harsha240yeager/1024-HDC/issues/33) ARM NEON · [#34](https://github.com/harsha240yeager/1024-HDC/issues/34) real encoder · [#35](https://github.com/harsha240yeager/1024-HDC/issues/35) PL-rail energy.

Recreate issues: `powershell scripts/create_date2027_issues.ps1` (or `bash scripts/create_date2027_issues.sh` on Linux).

---

## 11. Related repo docs

- `docs/DATE2027_ISSUES.md` — live experiment checklist for DATE 2027
- `docs/PAPER_DISCUSSION_GUIDE.md` — advisor meeting / mechanism detail
- `docs/REPRODUCIBILITY.md` — artifact tiers and claim checker
- `docs/DATE_REVISION_PLAN.md` — combined-paper revision history (#1–#11)
- `docs/HDC_Research_End_to_End_Guide.md` — RTL module map (pre-results)

**Camera-ready authors:** `Research-paper` git history (`0eb602e`) — not in blind submission tree.
