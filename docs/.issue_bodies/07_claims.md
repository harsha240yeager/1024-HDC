## Priority: P2

Runtime masking does **not** reduce LUT count or whole-board J21 energy today.

## Path A

Compact datapath RTL (process only retained bits); remeasure area/timing/power.

## Path B (if no RTL change)

Reframe contribution as **runtime accuracy-preserving bit-position selection** on fixed-width datapath. PL vs ARM energy = platform comparison, not pruning benefit.

## Paper

Update title/abstract/intro/conclusion to match chosen path.

Plan: [Phase 7](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-7--align-claims-with-what-pruning-changes)

Also: [Research-paper #1](https://github.com/harsha240yeager/Research-paper/issues/1)
