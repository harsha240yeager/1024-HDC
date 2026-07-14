## Priority: P1 (blocked by #1)

Replace tautological Twist 2 (identical masks @128b; lossless @512b) with **accuracy-stressing cross-subject transfer**.

## Design

- Train pooled mask on S1–S18 TRAIN only; eval S19–S36 TEST (HDC-2 split)
- Keep ratios (bits): **32, 64, 96, 128, 192, 256**
- Compare: **Random** / **Pooled Fisher** / **Local oracle** per held-out subject

## Success

Find ≥1 keep ratio where masks differ, pruning hurts, and pooled retains most of local-oracle benefit.

## Target claim

> On unseen subjects, pooled Fisher masks retain most of the local-oracle benefit under accuracy-stressing compression.

Plan: [`DATE_REVISION_PLAN.md` Phase 2](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-2--cross-subject-transfer-under-accuracy-stress)
