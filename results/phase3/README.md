# Phase 3 — Measurement infrastructure

**Batch bench: COMPLETE** (June 2026, SG DMA + timing-clean bitstream)  
**EMG replay: PASS** (June 2026, 658k windows, **74.24%** RTL encoder)  
**Full Phase 3 (paper):** energy pending

**Dual baseline:** Stage B **90.30%** (Python reference) vs RTL encoder **74.24%** (board).
See `docs/Baseline_vs_RTL_Encoder.md`.

**Prerequisite:** Phase 2 complete (`results/phase2/`).

## Close checklist — batch measurement (minimum)

| # | Task | Status |
|---|------|--------|
| 1 | Rebuild bench ELF (`Final_HDC_dma_bench.elf`) | **DONE** — `board/HDC_DMA/build_sw.sh` |
| 2 | Program timing-clean bitstream (physopt) | **DONE** — `design_1_wrapper.bit` @ June 2026 |
| 3 | Run bench on board | **DONE** — JTAG readback (`run_phase3_bench.sh`) |
| 4 | Verify pass lines in log | **DONE** — see `board_bench.txt` |
| 5 | Save + commit `board_bench.txt` | **DONE** |

## Full Phase 3 close (paper)

| # | Task | Output | Status |
|---|------|--------|--------|
| 6 | Energy (INA219 + shunt on Vcc_int) | `energy_batch.txt` + fill `energy_setup.txt` | **NOT DONE** — hardware pending |
| 7 | Full EMG replay on board | `board_emg_replay.txt` | **PASS** — 488550/658004, 74.24%, Δ0.00% (2026-06-23) |

Scaffolds: `scripts/export_emg_board_vectors.py`, `scripts/regenerate_emg_protos.py`,
`scripts/pack_emg_ddr_from_header.py`, `sw/hdc_emg_board_test.c`, `run_phase3_emg.sh`.

### EMG board pass criteria

| Check | Criterion |
|-------|-----------|
| Board PASS | \|board_acc − export_ref\| ≤ 0.5% |
| Export engine | `hdc_ref` (default) — matches `encoder_top.sv` |
| Stage B 90.30% | Python reference only — **not** board pass gate |
| Paper framing | `docs/Baseline_vs_RTL_Encoder.md` |

**Export ref (fixed protos, June 2026):** **74.24%** (488,550 / 658,004 correct).

### Prototype training fix (June 2026)

Offline class prototypes use `bundle_majority_unlimited()` — RTL `bundle_unit`
saturates at 6 bits (fine for 20-pair queries, not for 20k+ training windows).
Early exports → all-zero protos → bogus **~59%** accuracy. See GitHub commits
`c77943f`, `452a5ec`.

```bash
bash scripts/prep_emg_board_test.sh   # full export (~4 h, one-time)
python3 scripts/regenerate_emg_protos.py --header sw/emg_board_vectors.h.full
python3 scripts/pack_emg_ddr_from_header.py --header sw/emg_board_vectors.h.full
cd board/HDC_DMA && bash build_sw.sh && bash run_phase3_emg.sh
```

## Results files

| File | Description |
|------|-------------|
| `board_bench.txt` | **Primary** — batch measurement close-out |
| `board_emg_replay.txt` | EMG v2 **PASS** — 74.24% RTL encoder |
| `logs/board_emg_replay_v1.log` | Historical v1 subset run (~59%, pre-fix) |
| `energy_batch.txt` | *(template)* until INA219 measured |
| `logs/` | Raw JTAG logs |
