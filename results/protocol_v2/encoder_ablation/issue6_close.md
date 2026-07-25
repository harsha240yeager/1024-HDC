## Issue #6 complete (Path B encoder ablation)

**Decision:** keep RTL encoder; no BSC in PL (Path A skipped).

**Artifacts:** `results/protocol_v2/encoder_ablation/`
- Runner: `python_ref/run_encoder_ablation.py`

### Spatial mean (S1–S5, 15k random TEST/subject)

| Step | Acc | Δ vs prev |
|------|-----|-----------|
| Stage B literature (full test) | 90.17% | — |
| Stage B @ HDC-2 | 89.37% | −0.80 |
| + item-mem seed 42 | 90.82% | +1.45 |
| + 16-level CiM | 90.26% | −0.56 |
| RTL item mem + 4 binds | 73.28% | **−16.98** |
| RTL 20 binds (deployed) | 72.89% | −0.39 |

Dominant gap = encoding/item-memory model (~17 pp), not feature-grid bind count.

Manuscript table `tab:encoder` added. Closing.
