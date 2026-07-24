# Issue 5 — active-bit ablation

Generated: 2026-07-23T13:45:09Z
Protocol: **HDC-2** · Engine: **hdc_ref**
Gap keep=0.125 (128 bits @ D=1024)

## Why support is sparse (~200–260 @ D=1024)

- Continuous value item memory flip budget: **D/n_levels = 64**
- Value table active bits (across 16 levels): **316**
- Mean per-(channel,feature) value-path active bits: **316.0**
- Universe of single-record binds active support: **1019**
- After 20-bind majority bundling, window HVs use far fewer positions (see table).

> Continuous value item memory only walks a Hamming path of length ~D/n_levels between v_min and v_max; each (c,f) slot therefore can flip at most that many output bits when the level changes. Twenty-slot majority bundling further collapses weakly contested bits.

## Spatial means

| seed | D | Active (pooled) | Single-record | Fisher@gap | Uniform rand | Fair rand | Gap vs uni (pp) | Gap vs fair (pp) | keep=0.5 lossless |
|------|---|-----------------|---------------|------------|--------------|-----------|-----------------|------------------|-------------------|
| 1 | 1024 | 202 | 1019 | 73.29% | 65.63% | 71.89% | +7.66 | +1.40 | yes |
| 7 | 1024 | 208 | 1022 | 72.43% | 63.51% | 71.05% | +8.92 | +1.37 | yes |
| 21 | 1024 | 209 | 1019 | 72.07% | 66.54% | 71.78% | +5.53 | +0.30 | yes |
| 42 | 512 | 96 | 508 | 72.38% | 64.35% | 71.26% | +8.04 | +1.12 | yes |
| 42 | 1024 | 209 | 1019 | 72.58% | 64.55% | 71.33% | +8.04 | +1.25 | yes |
| 42 | 2048 | 417 | 2042 | 76.11% | 69.91% | 75.04% | +6.21 | +1.07 | yes |

## Lossless keep=0.5

Constant bits outside the active support never change Hamming distance. Whenever `active_support ≤ D/2`, any mask that retains all active bits (including Fisher @ keep=0.5) matches full-width accuracy.

## Fair random baseline

`mask_random_from_support()` samples keep-bits **only from positions that vary** on encoded windows. Uniform random over all D bits wastes draws on frozen bits; the fair baseline removes that artifact.

## Regenerate

```bash
python3 python_ref/run_active_bit_ablation.py --quick
python3 python_ref/run_active_bit_ablation.py
```
