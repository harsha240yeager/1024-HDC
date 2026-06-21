# Phase 3 energy measurement setup

Measure **static** and **dynamic** energy on ZedBoard for the DMA stream inference path.

## Hardware

| Item | Connection |
|------|------------|
| INA219 breakout | I²C to PS (typically `/dev/i2c-*`, address `0x40`) |
| Shunt resistor | In series with **Vcc_int** (1.0 V PL rail) |
| Scope (optional) | Verify batch window timing for integration bounds |

**Important:** Do not shunt the main 3.3 V or 1.8 V PS rails without understanding
current budget. Vcc_int is the PL core rail targeted for dynamic power comparison.

## Procedure

1. **Static power:** Program bitstream, hold HDC idle (no DMA), sample INA219 for
   `T_static` seconds (e.g. 5 s). Record mean power `P_static`.

2. **Dynamic batch:** Run `run_batch_bench.sh` (or a fixed `BATCH_WINDOWS` build)
   while logging INA219 at ≥100 Hz. Mark batch start/stop via GPIO or UART timestamp.

3. **Integration:**  
   `E_dynamic = ∫ (P_total − P_static) dt` over the batch window only.  
   `E_per_window = E_dynamic / BATCH_WINDOWS`

4. **Record:** Save raw CSV + summary to `results/phase3/energy_batch.txt`:

   ```
   shunt_mohm: ...
   vcc_int_v: ...
   batch_windows: ...
   p_static_mw: ...
   e_dynamic_mj: ...
   e_per_window_uj: ...
   ```

## Software scaffold (TODO)

- `scripts/ina219_log.py` — I²C sampler during board run
- Tie batch marker to magic write @ `0x00100204` (status=0 → running, status=1 → done)

## Safety

- Verify shunt polarity and INA219 bus voltage range before energizing.
- Use a shunt sized for ~100–500 mA PL current (typical for xc7z020 @ 100 MHz).
