# Phase 3 energy measurement setup

Measure **static** and **dynamic** energy on ZedBoard for the DMA stream inference path.

## Raspberry Pi + INA219 (recommended if you have a Pi)

Use the Pi as the **I²C host** for INA219. The **ZedBoard bench still runs on Ubuntu** (`bsp-lab`) over JTAG — two machines, coordinated by hand.

### Pi shopping list

| Item | Notes |
|------|--------|
| Raspberry Pi (any 3/4/5) | Native I²C on GPIO — **no USB-I2C dongle** |
| INA219 breakout | [Adafruit #904](https://www.adafruit.com/product/904) |
| Jumper wires | Pi GPIO → INA219 |

### Pi → INA219 wiring (3.3 V I²C)

| Pi pin (BCM) | Physical pin | INA219 |
|--------------|--------------|--------|
| 3.3V | 1 | VCC |
| GND | 6 | GND |
| GPIO2 (SDA) | 3 | SDA |
| GPIO3 (SCL) | 5 | SCL |

### Power path (12 V — unchanged)

```text
12V (+) ──► INA219 Vin+ ──► INA219 Vin− ──► ZedBoard barrel (+)
12V (−) ─────────────────────────────────► ZedBoard GND
```

Pi and ZedBoard share **GND** if the Pi is powered from the same bench (optional but good practice: connect Pi GND to ZedBoard GND).

### Enable I²C on the Pi (once)

```bash
sudo raspi-config          # Interface Options → I2C → Enable → reboot
sudo apt install -y python3-pip i2c-tools
pip3 install smbus2
sudo usermod -aG i2c $USER   # log out and back in

# Verify INA219 @ 0x40
i2cdetect -y 1
```

### Two-machine measurement

**Terminal A — Ubuntu (`bsp-lab`)** — ZedBoard JTAG:

```bash
cd ~/1024-HDC
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
cd board/HDC_DMA && bash build_sw.sh && cd ../..

# Once per session: program PL, leave board idle
bash board/HDC_DMA/run_phase3_program_pl.sh
```

**Terminal B — Raspberry Pi** — clone/sync repo, run logger:

```bash
cd ~/1024-HDC          # git clone or rsync from Ubuntu
pip3 install smbus2

export INA219_BUS=1    # almost always 1 on Pi
export INA219_SHUNT_MOHM=100
export INA219_V_RAIL=12.0

bash scripts/run_energy_log_pi.sh
```

When the Pi script counts down, **immediately on Ubuntu** run:

```bash
bash board/HDC_DMA/run_phase3_bench_load.sh
```

Output on Pi (or sync to Ubuntu):

- `results/phase3/logs/ina219_static.csv`
- `results/phase3/logs/ina219_batch.csv`
- `results/phase3/energy_batch.txt`

**Single-machine alternative:** If the Pi also has Vivado/XSDB and the ZedBoard USB cable, you can run everything on the Pi — uncommon; the split setup above is the usual lab layout.

---

## Start here (USB-I2C on Ubuntu — no Pi)

### Shopping (if lab has nothing)

| Item | Link |
|------|------|
| INA219 breakout | [Adafruit #904](https://www.adafruit.com/product/904) |
| USB→I²C (FT232H replacement) | [MCP2221A #4471](https://www.adafruit.com/product/4471) or [CP2112 ~$10](https://www.amazon.com/MCU-2112-Communication-Evaluation-Adapter-Raspberry/dp/B0FDKNZ5LN) |

### Wiring (12 V method — do this first)

```text
12V adapter (+) ──► INA219 Vin+ ──► INA219 Vin− ──► ZedBoard barrel (+)
12V adapter (−) ─────────────────────────────────► ZedBoard GND

USB-I2C: 3.3V, GND, SDA, SCL → INA219 (same 3.3V domain)
```

Do **not** power the ZedBoard until INA219 + I²C wiring is checked.

### Commands (Ubuntu workstation `bsp-lab`)

```bash
cd ~/1024-HDC
pip install smbus2
sudo modprobe i2c-dev    # if needed

# 0) Wire + verify INA219 (must show PASS)
bash scripts/energy_preflight.sh

# 1) Set bus from preflight output
export INA219_BUS=10          # your number
export INA219_SHUNT_MOHM=100  # Adafruit built-in 0.1 Ω
export INA219_V_RAIL=12.0

# 2) Build bench ELF if needed
export HDC_VIVADO_ROOT="/path/to/FInal_HDC"
cd board/HDC_DMA && bash build_sw.sh && cd ../..

# 3) Full measurement (program PL → static log → dynamic log + bench load → summary)
bash scripts/run_energy_measure.sh
```

The script **programs PL once**, logs **idle static** power, then logs while running
**bench load-only** (no bitstream reprogram during the dynamic capture).

Output: `results/phase3/energy_batch.txt` + CSVs under `results/phase3/logs/`.

**Second run same session:** `ENERGY_SKIP_PROGRAM=1 bash scripts/run_energy_measure.sh`

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

## Software

- `scripts/ina219_log.py` — I²C sampler + integration → `energy_batch.txt`
- `scripts/run_energy_log_pi.sh` — **Pi**: static + dynamic log (bench on Ubuntu)
- `scripts/run_energy_measure.sh` — **Ubuntu all-in-one** (USB-I2C + JTAG same host)
- `scripts/energy_preflight.sh` — verify INA219 on `/dev/i2c-N`

## Safety

- Verify shunt polarity and INA219 bus voltage range before energizing.
- Use a shunt sized for ~100–500 mA PL current (typical for xc7z020 @ 100 MHz).
