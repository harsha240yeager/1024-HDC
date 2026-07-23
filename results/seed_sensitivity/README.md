# Issue 4 — item-memory seed sensitivity

Generated: 2026-07-22T06:19:26Z
Protocol: **HDC-2** · Engine: **hdc_ref**
D=1024  CNT_W=6  gap keep=0.125 (128 bits)

## Spatial mean (5 subjects)

| item_mem_seed | Full-width acc | Active support | Fisher @128 | Random @128 | Gap (pp) |
|---------------|----------------|----------------|-------------|-------------|----------|
| 1 | 73.37% | 203 | 73.37% | 65.66% | +7.71 |
| 7 | 72.42% | 210 | 72.42% | 63.62% | +8.79 |
| 21 | 72.22% | 209 | 72.22% | 66.67% | +5.55 |
| 42 | 72.65% | 209 | 72.65% | 64.71% | +7.94 |

## Keep-ratio curve (spatial mean accuracy)

| item_mem_seed | keep=0.125 | keep=0.25 | keep=0.5 | keep=1 |
|---|---|---|---|---|
| 1 | 73.37% | 73.37% | 73.37% | 73.37% |
| 7 | 72.42% | 72.42% | 72.42% | 72.42% |
| 21 | 72.22% | 72.22% | 72.22% | 72.22% |
| 42 | 72.65% | 72.65% | 72.65% | 72.65% |

## Regenerate

```bash
python3 python_ref/run_seed_sensitivity.py --quick
python3 python_ref/run_seed_sensitivity.py --seeds 1,7,21,42
```
