# DATE 2027 — strong-accept experiment tracker

**Target:** DATE 2027 submission (~Sep 2026) · **Strategy:** one combined manuscript after experiments  
**Epic:** [#20](https://github.com/harsha240yeager/1024-HDC/issues/20)  
**Split plan:** [`SPLIT_PAPER_PLAN.md`](SPLIT_PAPER_PLAN.md)

Prior revision track (#1–#11) is largely complete; this track adds experiments required for **strong accept** of both split papers folded into the combined DATE submission.

---

## Priority order (do experiments in this sequence)

| # | Issue | Status | Paper | Blocker |
|---|-------|--------|-------|---------|
| 1 | [#21](https://github.com/harsha240yeager/1024-HDC/issues/21) Stage-B iso-density (S1) | ✅ | 2 | **Yes** |
| 2 | [#22](https://github.com/harsha240yeager/1024-HDC/issues/22) Stage-B ranking baselines | ✅ | 2 | **Yes** |
| 3 | [#23](https://github.com/harsha240yeager/1024-HDC/issues/23) Three-baseline hero figure | ✅ | 2 | Medium |
| 4 | [#24](https://github.com/harsha240yeager/1024-HDC/issues/24) Active-support mechanism | ✅ | 2 | Medium |
| 5 | [#25](https://github.com/harsha240yeager/1024-HDC/issues/25) Encoder redundancy doc | ✅ | 2 | Medium |
| 6 | [#26](https://github.com/harsha240yeager/1024-HDC/issues/26) Silicon seeds 1–9 | ✅ predict + seed 0 board; 1–9 board lab | Both | **Yes** |
| 7 | [#27](https://github.com/harsha240yeager/1024-HDC/issues/27) Silicon seed automation | ✅ script | Both | Enables #26 |
| 8 | [#28](https://github.com/harsha240yeager/1024-HDC/issues/28) Design narrow/gated RTL | ✅ Option E (baked permutation, bit-exact) — `docs/H1_narrow_datapath_design.md` | 1 | **Yes** |
| 9 | [#29](https://github.com/harsha240yeager/1024-HDC/issues/29) Implement + synth | ⏳ RTL + ModelSim co-sim done; synth still open | 1 | **Yes** |
| 10 | [#30](https://github.com/harsha240yeager/1024-HDC/issues/30) Co-sim + golden | ✅ identity 500/500 + anchor C 500/500 | 1 | **Yes** |
| 11 | [#31](https://github.com/harsha240yeager/1024-HDC/issues/31) Board eval vs keep | ⏳ | 1 | **Yes** |
| 12 | [#32](https://github.com/harsha240yeager/1024-HDC/issues/32) Pareto figure | ⏳ | 1 | Medium |
| 13 | [#36](https://github.com/harsha240yeager/1024-HDC/issues/36) Integrate manuscript | ⏳ | Both | **Yes** |
| 14 | [#37](https://github.com/harsha240yeager/1024-HDC/issues/37) Claim checker + figures | ⏳ | Both | **Yes** |
| 15 | [#38](https://github.com/harsha240yeager/1024-HDC/issues/38) DATE submit checklist | ⏳ | Both | **Yes** |

### Optional (P2 — after P0/P1 or if time permits)

| Issue | Paper | Notes |
|-------|-------|-------|
| [#33](https://github.com/harsha240yeager/1024-HDC/issues/33) ARM NEON baseline | 1 | Closes unfair-software critique |
| [#34](https://github.com/harsha240yeager/1024-HDC/issues/34) Real per-feature encoder | 2 | Large scope; #21 may suffice |
| [#35](https://github.com/harsha240yeager/1024-HDC/issues/35) PL-rail energy | 1 | Post-DATE journal |

---

## Success gates

**Paper 2 strong:** Stage-B iso-density shows whether criteria separate on dense support; three random baselines; mechanism (327 vs 209) quantified.

**Paper 1 strong:** Narrow/gated RTL ≥10% LUT **or** measurable energy/latency at keep=0.125 (≤0.5 pp accuracy loss); ≥5 silicon random seeds.

**Combined DATE strong:** Both gates + integrated 6-page blind manuscript + claim checker PASS.

---

## Parallelization notes

- **Python track (#21–#25):** can run in parallel with **RTL design (#28)** once protocol is frozen.
- **Silicon (#26):** needs board access; script (#27) can be written while Python runs.
- **Manuscript (#36–#38):** blocked until P0 experiment results exist (or explicit waiver on epic #20).

---

## Legacy

- [#3](https://github.com/harsha240yeager/1024-HDC/issues/3) — Python random-mask stats done; FPGA seeds superseded by **#26**.
- Revision track [#1–#11](https://github.com/harsha240yeager/1024-HDC/issues) — see [`DATE_REVISION_PLAN.md`](DATE_REVISION_PLAN.md).

---

## Recreate issues

```powershell
powershell -File scripts/create_date2027_issues.ps1
```

Issue bodies: `docs/.issue_bodies/date2027/`

---

## Issue #26 — silicon seed prediction (in progress)

**Predictor:** `python_ref/predict_twist1_silicon_seeds.py`  
**Automation:** `scripts/run_silicon_random_seeds.sh` (also closes #27)

```bash
# Python export-ref prediction (all seeds 0–9; ~1–3 h first run, cached after)
python3 python_ref/predict_twist1_silicon_seeds.py --from-dataset

# Optional: board replay when ZedBoard available
bash scripts/run_silicon_random_seeds.sh --board --seeds 1-9 --resume
```

**Method:** Pooled random mask @ keep=0.125 (same as `patch_emg_anchor.py` / board).
Seed 0 validated **board == export ref (Δ0.00 pp)** → predicted silicon = export ref for seeds 1–9 until measured.

**Outputs:** `results/protocol_v2/twist1_silicon/seed_summary.json`, per-seed `prediction.json`
