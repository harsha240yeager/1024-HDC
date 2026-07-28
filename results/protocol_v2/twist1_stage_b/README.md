# Stage B iso-density ablation (issue #21 / S1)

Literature **Stage B BSC** encoder (~89.46% unpruned spatial mean) under Protocol HDC-2.
Twist 1: Fisher-informed vs random-all masks at fixed keep ratio (30 random seeds, 5 subjects).

## Keep grid summary

| Keep | Bits | Informed | Random (mean) | Gap (pp) | Bootstrap 95% CI | + gap subjects | Target ≥5 pp |
|------|------|----------|---------------|----------|------------------|----------------|--------------|
| 0.125 | 128 | 89.01% | 86.19% | **+2.82** | [+0.44, +4.98] | 4/5 | FAIL |
| 0.25 | 256 | 89.34% | 88.32% | **+1.02** | [+0.09, +2.03] | 4/5 | FAIL |
| 0.50 | 512 | 89.46% | 88.96% | **+0.50** | [+0.05, +0.94] | 3/5 | FAIL |

Reference (sparse hdc_ref RTL encoder @ keep=0.125): **+6.90 pp** ([`twist1_keep0125_30seed/`](../twist1_keep0125_30seed/)).

## Decision (issue #21)

**Criteria separate on Stage B, but the Fisher signal weakens with denser support.**

- At keep=0.125 (128 bits), informed beats random by **+2.82 pp** (bootstrap CI excludes 0; 4/5 subjects positive). This is **not a tie** — bit-position choice still matters on the dense-support encoder.
- The effect is **much smaller** than on hdc_ref (+6.90 pp at the same keep): roughly **41% of the sparse-encoder gap**, consistent with dense active support diluting positional discriminability.
- As keep increases, the gap **monotonically shrinks** (+2.82 → +1.02 → +0.50 pp) and approaches noise; at keep=0.5 only 3/5 subjects favor informed.
- **Paper 2 gate (≥5 pp): FAIL** on Stage B at all tested keeps. The falsification outcome is: dense support **attenuates** but does not **eliminate** the iso-density effect at K=128.

Random-support baseline (third arm in the issue spec) is **deferred** — not implemented for hdc_ref or Stage B yet; does not change the informed-vs-random-all conclusion above.

## Artifacts

| Keep | Directory |
|------|-----------|
| 0.125 | [`../twist1_stage_b_keep0125/`](../twist1_stage_b_keep0125/) |
| 0.25 | [`../twist1_stage_b_keep0250/`](../twist1_stage_b_keep0250/) |
| 0.50 | [`../twist1_stage_b_keep0500/`](../twist1_stage_b_keep0500/) |

Stage B unpruned baseline: [`../stage_b_hdc2/`](../stage_b_hdc2/)

## Regenerate

```bash
bash scripts/run_twist1_stage_b_keep_grid.sh
bash scripts/run_twist1_stage_b_keep_grid.sh --keep 0.25   # single point
python3 python_ref/tools/subject_level_stats.py \
  --results results/protocol_v2/twist1_stage_b_keep0125/twist1_results.json
```
