# Issue 6 - Path B encoder ablation (Stage B -> RTL)

Generated: 2026-07-25T10:55:58Z
Protocol: **HDC-2** · D=1024 · subjects=[1, 2, 3, 4, 5]

Path A (BSC in PL) is **out of scope**. This table explains the ~17 pp gap
between the literature BSC reference and the deployed RTL encoder.

## Spatial mean

| Step | Configuration | Test set | Acc | Δ vs prev (pp) |
|------|---------------|----------|-----|----------------|
| `stage_b_literature_fulltest` | Stage B BSC (literature protocol) | full_recording | **90.17%** | - |
| `stage_b_hdc2` | Stage B BSC @ HDC-2 | disjoint | **89.37%** | -0.80 |
| `stage_b_hdc2_seed42` | Stage B + item-mem seed 42 | disjoint | **90.82%** | +1.45 |
| `stage_b_hdc2_16levels` | Stage B + 16-level CiM | disjoint | **90.26%** | -0.56 |
| `rtl_4bind` | RTL item mem + 4 binds | disjoint | **73.28%** | -16.98 |
| `rtl_20bind` | RTL encoder (20 binds) | disjoint | **72.89%** | -0.39 |

## What moves the needle

- **Protocol / seed / 21→16 levels:** small (±1–2 pp).
- **Stage-B `iM⊕CiM` records → RTL item memory + Eq. 3.1 bind (4 channels):**
  **−17.0 pp** (90.26% → 73.28%) — the dominant gap.
- **4 → 20 binds (feature grid):** only **−0.4 pp** (73.28% → 72.89%).

So the literature↔deployment gap is mostly the **encoding/item-memory model**,
not the extra feature slots.

## Regenerate

```bash
python3 python_ref/run_encoder_ablation.py --quick
python3 python_ref/run_encoder_ablation.py
```
