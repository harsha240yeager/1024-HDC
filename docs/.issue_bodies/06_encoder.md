## Priority: P2

RTL encoder ~72.65% vs Stage-B BSC ~90% — explain (Path B) or fix (Path A).

## Path A (stronger) — skipped

Implement BSC-style encoder in PL; rerun pruning. **Out of scope.**

## Path B (acceptable) — DONE

Controlled ablation: Stage B → stepwise → RTL under HDC-2.

| Configuration | Acc |
|---------------|-----|
| Literature BSC (full test) | 90.17% |
| Stage B @ HDC-2 | 89.37% |
| + item-mem seed 42 | 90.82% |
| + 16-level CiM | 90.26% |
| RTL item mem + 4 binds | **73.28%** (−17.0 pp) |
| RTL 20 binds (deployed) | **72.89%** (−0.4 pp) |

**Takeaway:** gap is Stage-B records → RTL item memory / Eq. 3.1 bind, not 4→20 binds.

Outputs: `python_ref/run_encoder_ablation.py` → `results/protocol_v2/encoder_ablation/`
