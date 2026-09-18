# Issue 40 — native D vs K=128 gather (HDC-2)

Generated: 2026-09-18T07:17:26Z
Protocol: **HDC-2** · CNT_W=6 · item_mem_seed=42
Subjects: [1, 2, 3, 4, 5]
Test cap: all windows/subject

## Spatial mean (S1–S5)

| Engine | Mode | Spatial mean | Pooled |
|--------|------|--------------|--------|
| hdc_ref | native_D128_full | 68.08% | 68.13% |
| hdc_ref | native_D256_full | 69.76% | 69.82% |
| hdc_ref | native_D1024_full | 72.65% | 72.78% |
| hdc_ref | d1024_fisher_k128_masked | 72.65% | 72.78% |
| hdc_ref | d1024_option_e_k128_gather | 72.65% | 72.78% |
| stage_b | native_D128_full | 84.81% | 84.73% |
| stage_b | native_D256_full | 89.99% | 90.29% |
| stage_b | native_D1024_full | 89.46% | 89.67% |
| stage_b | d1024_fisher_k128_masked | 89.01% | 89.36% |
| stage_b | d1024_option_e_k128_gather | 89.01% | 89.36% |

## Interpretation

- **native_D***: encode and classify entirely at hypervector width D.
- **d1024_fisher_k128_masked**: Fisher free-choice mask @ keep=0.125 on D=1024 queries.
- **d1024_option_e_k128_gather**: same decisions as masked path (gather bit-exact).
- Compare native D=256 to Hook A D=256 @ CNT_W=6 (`protocol_v2/hook_a/`).

## Regenerate

```bash
python3 python_ref/run_native_d_sweep.py --quick
python3 python_ref/run_native_d_sweep.py
```
