## Priority: P1 (blocked by #1)

Compare Fisher ranking against stronger baselines (not random alone).

## Methods to implement

- [x] Variance ranking
- [x] Mutual information
- [x] Class-mean separation
- [x] Prototype disagreement frequency
- [x] Per-bit entropy
- [x] Random (full 1024) vs random (active support)
- [x] Fisher (current)
- [ ] Learned mask (optional — skipped)

## Table

Method × 128-bit accuracy × ranking cost × requires retraining?

Outputs: `results/protocol_v2/ranking_baselines/`

Plan: [Phase 5b](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#5b--ranking-baselines-128-bit-accuracy)

Related: #5 (active-bit support)
