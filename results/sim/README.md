# Simulation result summaries

Co-simulation harnesses are run locally / in CI; full waveforms stay out of git
(see `.gitignore` for `sim/waves/*.vcd`).

## Harness status (ModelSim, seed 42 vectors)

| Harness | Cases | Status |
|---------|-------|--------|
| `sim/run_cosim.do` | 1000 (default) | PASS |
| `sim/run_bundle_cosim.do` | 500 | PASS |
| `sim/run_am_cosim.do` | 500 | PASS |
| `sim/run_encoder_cosim.do` | 500 | PASS |
| `sim/run_core_cosim.do` | 500 | PASS |
| `sim/run_core_axi_cosim.do` | 200 | PASS |
| `sim/run_stream_cosim.do` | 200 | PASS |

Regenerate vectors: `python python_ref/generate_vectors.py --core --out-dir python_ref/vectors/cosim_core --count 200 --seed 42`
