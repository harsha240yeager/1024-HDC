# Issue #41 — paper table (body text)

| Quantity | Baseline (D=1024) | Narrow (K=128 gather) |
|----------|-------------------|------------------------|
| OOC core LUT | 28,600 | 3,794 (7.5×) |
| — encoder | 25,672 | 3,328 |
| — popcount AM | 2,672 | 466 |
| Integrated PL LUT | 35,206 | 10,601 |
| Core cycles / window | 287 | 63 |
| Core time @ 100 MHz | 2.87 µs | 0.63 µs |
| Batch DMA latency | ~4 µs/w | ~2 µs/w |
| Single-window DMA | ~58 µs | ~56 µs |

OOC core WNS: baseline **0.781 ns**; narrow core **1.661 ns** (post-synth, 100 MHz constraint).
