## Goal

Complete **all experiments required for strong accept** of the split-paper plan
(hardware + science) and fold results into the **combined DATE 2027** manuscript
before submission (~Sep 2026).

**Plan:** [docs/SPLIT_PAPER_PLAN.md](docs/SPLIT_PAPER_PLAN.md)

## Priority order (do not reorder without cause)

| Order | Issue | Paper | Blocker for strong accept |
|------:|-------|-------|---------------------------|
| 1 | Stage-B iso-density (S1) | Paper 2 | **Yes** — dense-support falsification |
| 2 | Stage-B ranking baselines | Paper 2 | **Yes** — criteria separate (or confirm tie) |
| 3 | Three-baseline hero figure | Paper 2 | Medium — clarity |
| 4 | Active-support mechanism table | Paper 2 | Medium — mechanism (327 vs 209) |
| 5 | Encoder redundancy disclosure | Paper 2 | Medium — reviewer trap |
| 6 | Silicon random seeds 1–9 | Both | **Yes** — hardware stats |
| 7 | Silicon seed automation script | Both | Enables #6 |
| 8 | Design narrow/gated `popcount_am` | Paper 1 | **Yes** — hardware win |
| 9 | Implement + synth narrow/gated RTL | Paper 1 | **Yes** |
| 10 | Co-sim + golden verify (new RTL) | Paper 1 | **Yes** |
| 11 | Board LUT/energy/latency vs keep | Paper 1 | **Yes** |
| 12 | Pareto figure + util compare script | Paper 1 | Medium |
| 13 | Integrate results into manuscript | Both | **Yes** before submit |
| 14 | Claim checker + figures refresh | Both | **Yes** before submit |
| 15 | DATE submission checklist | Both | **Yes** |

Optional (P2): ARM NEON (#33), real per-feature encoder (#34), PL-rail energy (#35).

## Success gates (from split plan)

**Paper 2 strong:** Stage-B iso-density shows whether criteria separate on dense
support; three random baselines reported; mechanism quantified.

**Paper 1 strong:** Narrow/gated RTL shows ≥10% LUT **or** measurable energy/latency
improvement at keep=0.125 with accuracy within 0.5 pp; ≥5 silicon random seeds.

**Combined DATE strong:** Both gates + integrated 6-page manuscript.

## Child issues

See [comment on #20](https://github.com/harsha240yeager/1024-HDC/issues/20) for numbered list #21–#38.

Live tracker: [docs/DATE2027_ISSUES.md](docs/DATE2027_ISSUES.md)
