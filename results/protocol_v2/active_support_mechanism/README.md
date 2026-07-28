# Issue 24 — active support mechanism (327 vs ~209)

Generated: 2026-07-28T13:08:10Z
Protocol: **HDC-2** · Engine: **hdc_ref** · D=1024
Primary item-memory seed: **42**

## Paper table (Discussion §5.2)

| Quantity | Positions (of 1024) |
|----------|---------------------|
| Value-table varying set — structural ceiling | **327** |
| Bundled queries, uniform random envelope | **299** |
| Bundled queries, independent per-slot levels | **319** |
| Bundled queries, real pooled data (5 subjects) | **203–210** (mean 207.7) |

## Mechanism (one paragraph)

The encoder's **structural ceiling** is the value item-memory table: only **327** of 1024 bit positions can ever flip under any input, because channel/feature tables enter as XOR constants and the continuous value table walks a Hamming path of length ~D/n_levels (64 for 16 levels). Synthetic bundled windows that freely sample levels approach that ceiling (299–319 with n=8000 windows); **real EMG envelopes only exercise 203–210 positions** (~20% of D), which is data coverage, not bundling. Hence keep=512 is lossless (512 > ~209 active) and uniform random @ keep=128 wastes most draws on frozen bits.

## Per seed (value-table ceiling)

| Seed | Value table | Per-slot path mean | Uniform synth | Independent synth |
|------|-------------|--------------------|--------------|--------------------|
| 1 | 316 | 316 | — | — |
| 7 | 339 | 339 | — | — |
| 21 | 330 | 330 | — | — |
| 42 | 327 | 327 | 299 | 319 |

## Real EMG (from seed sensitivity)

| Seed | Spatial mean active support |
|------|----------------------------|
| 1 | 203.0 |
| 7 | 209.8 |
| 21 | 208.6 |
| 42 | 209.4 |

Source: [`seed_sensitivity_results.json`](../../seed_sensitivity/seed_sensitivity_results.json)

## Regenerate

```bash
python3 python_ref/run_active_support_mechanism.py --quick
python3 python_ref/run_active_support_mechanism.py
```

Related: [`active_bits/`](../active_bits/) (issue #5), [`PAPER_DISCUSSION_GUIDE.md`](../../docs/PAPER_DISCUSSION_GUIDE.md) §5.2
