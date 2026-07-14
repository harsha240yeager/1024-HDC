## Priority: P2

RTL encoder ~74% vs Stage-B BSC ~90% — explain or fix.

## Path A (stronger)

Implement BSC-style encoder (or close approximation) in PL; rerun pruning study.

## Path B (acceptable)

Controlled ablation table: Stage B → stepwise changes → final RTL encoder.

| Configuration | Accuracy |
|---------------|----------|
| Literature BSC | ~90.3% |
| … stepwise … | |
| Final RTL | ~74.2% |

Plan: [Phase 6](https://github.com/harsha240yeager/1024-HDC/blob/main/docs/DATE_REVISION_PLAN.md#phase-6--encoder-gap-74-vs-90)
