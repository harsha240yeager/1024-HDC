# DATE Major Revision — Execution Plan

Ordered workflow for the post weak-reject DATE resubmission.  
**Master plan:** [`DATE_REVISION_PLAN.md`](DATE_REVISION_PLAN.md) · **Revision issues:** [#1–#11](https://github.com/harsha240yeager/1024-HDC/issues) · **DATE 2027 strong-accept epic:** [#20](https://github.com/harsha240yeager/1024-HDC/issues/20) ([`DATE2027_ISSUES.md`](DATE2027_ISSUES.md))

---

## Quick start

```bash
# Local gate (CI runs the same checks)
bash scripts/run_hdc2_gate.sh

# Create tracking issues (needs gh auth)
bash scripts/create_revision_issues.sh

# Phase 1 blocker — after split fix lands
python scripts/audit_split_leakage.py --config python_ref/config/emg_baseline_v2.json
```

**Rule:** Do not update paper headline numbers until Phase 1 HDC-2 reruns complete.

---

## Week 1 — Phase 1 (BLOCKER)

| Day | Task | Deliverable |
|-----|------|-------------|
| 1–2 | HDC-2 split in code + `emg_baseline_v2.json` | PR merged, CI green |
| 2 | `audit_split_leakage.py` → overlap = 0 | `results/protocol_v2/split_audit.json` |
| 3–4 | Python baseline + export + Fisher | `results/protocol_v2/` |
| 5–7 | Board replay + Hook A / Twist reruns | New silicon logs under `protocol_v2/` |

**Exit:** Issue #1 closed · HDC-2 gate PASS · board bit-exact vs new export ref.

---

## Week 2 — Phases 3 + 8

| Phase | Issue | Work |
|-------|-------|------|
| 3 | #3 | 20–30 random seeds, subject-level stats, FPGA seeds 0–9 |
| 8 | #8 | `docs/ENERGY_METHODOLOGY.md` |

---

## Week 3 — Phases 2, 4, 5

| Phase | Issue | Work |
|-------|-------|------|
| 2 | #2 | Cross-subject keep grid 32–256 bits, 36 subjects |
| 4 | #4 | Item-memory seeds {1, 7, 21, 42} |
| 5 | #5, #9 | Active-bit (~257) + ranking baselines |

---

## Week 4 — Phases 6, 7, 9–10

| Phase | Issue | Work |
|-------|-------|------|
| 6 | #6 | Encoder ablation table (Path B default) |
| 7 | #7 | Claim reframe — fixed-width datapath (Path B) |
| 10 | #10 | Fig 1 (5-class), latency/energy footnotes |

---

## Week 5 — Phases 11–12 + submit

| Phase | Issue | Work |
|-------|-------|------|
| 11 | #11 | `scripts/reproduce_paper.sh`, Zenodo tag |
| Paper | Research-paper #3–#4 | Title, abstract, §IV Protocol HDC-2 |

---

## CI / PR workflow

1. Branch from `main`: `feat/hdc2-phase-N-short-name`
2. Run `bash scripts/run_hdc2_gate.sh` before push
3. Open PR — template checks phase link + test plan
4. Merge when CI passes; update `DATE_REVISION_PLAN.md` status board
5. HDC-2 results go under `results/protocol_v2/` (do not overwrite HDC-1)

---

## Decision defaults (Sep 2026 deadline)

| Decision | Default |
|----------|---------|
| Encoder Path A vs B | **B** — ablation table |
| Claim Path A vs B | **B** — honest reframe |
| Boundary gap ±1 | Off unless audit shows edge risk |

---

## Status board

Copy to issue #1 or project board; update as phases complete.

| Phase | Status |
|-------|--------|
| 1 HDC-2 split + Tier 1 | ✅ complete — issue #1 closed |
| 1b Hook A + anchors | ✅ complete — `protocol_v2/hook_a/`, `protocol_v2/anchors/` |
| 2 Cross-subject | ✅ complete — 5-subj pilot (+1.02 pp) · 36-subj keep grid 32–256 bits (`protocol_v2/twist2_36_v2/`) · @32b pooled +2.59 pp vs local · 64+b lossless [#2](https://github.com/harsha240yeager/1024-HDC/issues/2) |
| 3 Random + stats | ✅ 30-seed Python + subject-level CI/Wilcoxon — `twist1_keep0125_30seed/` · silicon seeds 1–9 deferred · issue #3 |
| 4 Seeds | ✅ `results/seed_sensitivity/` — issue #4 |
| 5 Active bits | ✅ tooling + HDC-2 sweep (`results/protocol_v2/active_bits/`) · issue #5 |
| 6 Encoder | ✅ Path B ablation — `protocol_v2/encoder_ablation/` · issue #6 |
| 7 Claims | ⏳ issue #7 (Path B) |
| 8 Energy doc | ✅ `docs/ENERGY_METHODOLOGY.md` + paper Appendix — issue #8 |
| 9 Baselines | ✅ `results/protocol_v2/ranking_baselines/` · issue #9 |
| 10 Inconsistencies | ✅ Fig 5-class + metrics footnotes — issue #10 |
| 11 Repro artifact | ✅ `docs/REPRODUCIBILITY.md` · `scripts/reproduce_paper.sh` · `scripts/check_paper_numbers.py` (49/49) — issue #11 |
| Paper rewrite | ✅ title/abstract/claim reorg — Research-paper #2–#4 |
