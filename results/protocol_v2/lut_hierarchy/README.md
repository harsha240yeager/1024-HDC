# Issue 41 — LUT hierarchy and core cycles (full vs narrow)

Generated from committed Vivado OOC synth reports (`results/dsweep/`) and narrow
integrated utilization (`results/narrow_rtl/integrated_utilization_placed.rpt`).
No new place-and-route run.

## OOC core LUT (`hdc_core_top` vs `hdc_core_top_narrow`)

| Block | Baseline (D=1024) | Narrow (K=128 AM) |
|-------|-------------------|-------------------|
| **Core total** | **28,600** | **3,794** (7.5× smaller) |
| Encoder (`encoder_top`) | 25,672 | 3,328 |
| — bundle (`bundle_unit`) | 25,006 | 3,311 |
| Associative memory | 2,672 (`popcount_am`) | 466 (`popcount_am_narrow`) |
| Pruning mask | 256 | 0 (baked gather) |

Encoder width stays D=1024 in both bitstreams; the narrow win is almost entirely in the AM
(2,672 → 466 LUT) plus dropping `pruning_mask`.

## Stream + BD OOC (DMA path shell)

| Scope | Baseline LUT | Narrow LUT |
|-------|--------------|------------|
| `hdc_stream_wrapper*` | 28,963 | 4,153 |
| Stream FSM shell | 346 | 343 |
| BD wrapper + AXI cfg | 30,639 | 4,261 |
| — AXI-Lite cfg block | 1,683 | 133 |

## Integrated placed (Zynq PL)

| Bitstream | Slice LUTs | Source |
|-----------|------------|--------|
| Baseline Phase 3 | **35,206** | Deployed design / issue #31 summary |
| Narrow (anchor C) | **10,601** | `integrated_utilization_placed.rpt` |

## Core cycles @ 100 MHz (PL compute only)

| Path | Encode | Classify | **Total cycles** | **≈ µs** |
|------|--------|----------|------------------|----------|
| Baseline D=1024 | 23 | 264 | **287** | 2.87 |
| Narrow K=128 AM | 23 | 40 | **63** | 0.63 |

Classify formula: `N_CLASS × (2×WORDS + 1)` vs `N_CLASS × (2×K_WORDS + 1)` per `hdc_core_top*.sv`.

## Timing (WNS / WHS, OOC synth)

| Report | WNS (ns) | WHS (ns) |
|--------|----------|----------|
| Baseline core | 0.781 | 0.259 |
| Narrow core | 1.661 | 0.259 |
| Narrow integrated post-route | 1.011 | (see integrated_synth.log) |

## Board latency (system, not core-only)

| Metric | Baseline | Narrow |
|--------|----------|--------|
| Single-window DMA mean | 58 µs | 56 µs |
| Batch 200 windows mean | ~4 µs/w | ~2 µs/w |
| Phase 1 AXI-Lite poll (ref) | ~3 µs/w | same |

## Regenerate

```bash
python3 scripts/build_lut_hierarchy_issue41.py
```
