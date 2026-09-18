# Issue #40 — native width vs Option-E gather (HDC-2, hdc_ref)

CNT_W=6, item_mem_seed=42, full test windows S1–S5.

| Mode | Spatial mean | Pooled | Notes |
|------|--------------|--------|-------|
| Native D=128 encode+classify | **68.08%** | 68.13% | New committed baseline |
| Native D=256 encode+classify | **69.76%** | **69.82%** | Matches Hook A D=256 @ keep=1.0 (spatial); pooled matches H1 design note |
| Native D=1024 full width | 72.65% | 72.78% | RTL encoder reference |
| D=1024 Fisher K=128 (masked) | 72.65% | 72.78% | Same as ranking #9 @ keep=0.125 |
| D=1024 Option-E K=128 gather | 72.65% | 72.78% | Bit-exact vs masked (100% pred agreement) |

**Headline:** K=128 gather from D=1024 is **+2.89 pp** above native D=256 at half the AM width (spatial mean), not a smaller-D re-label of the same hypervector.
