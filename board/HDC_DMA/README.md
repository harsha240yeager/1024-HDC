# Vitis / ZedBoard workspace for Phase 2 DMA (not in this git repo).

The full board bring-up tree lives on the lab machine as a sibling workspace:

```
Desktop/Final HDC/HDC_DMA/
├── run_jtag.sh       # program PL + 200-case JTAG golden test
├── run_bench.sh      # DMA latency bench + JTAG readback
├── build.sh          # rebuild BSP, FSBL, golden + bench ELFs
├── platform/         # Vitis platform (Final_HDC)
└── app/              # DMA golden + bench applications
```

Software sources and measured results are tracked in this repo under `sw/` and
`results/phase2/`. Host-side JTAG test Tcl is in `scripts/run_stream_golden_jtag.tcl`
(set `HDC_IDE` to `HDC_DMA/_ide` before running xsdb).
