# Phase 3 energy measurement setup

Measure **static** and **dynamic** energy on ZedBoard for the DMA stream inference path.

**What we measure:** whole-board **12 V input power** (PS + PL + peripherals) via the
ZedBoard’s on-board current-sense shunt — suitable for the **ARM-vs-PL total-system**
comparison. This is **not** an isolated Vcc_int (1.0 V PL-only) tap.

---

## ZedBoard connectors (find these on the silkscreen)

| Label | Name | Role |
|-------|------|------|
| **J20** | Barrel jack | 12 V power in (center-positive, 2.5 mm ID / 5.5 mm OD) |
| **SW8** | Power switch | ON connects 12 V to the board |
| **J21** | **Current sense** | 2-pin header across the on-board **10 mΩ** shunt in the 12 V path |
| **J3 / J4** | GND test points | Dedicated ground — use for Pi / scope return |
| **LD13** | Green LED | Power-good indicator |

Per the [ZedBoard Hardware User Guide](https://files.digilent.com/resources/programmable-logic/zedboard/ZedBoard_HW_UG_v2_2.pdf)
(§2.11.1): a **10 mΩ** resistor sits in series with the 12 V input; **J21 straddles
that resistor** so you can read the voltage drop without cutting any power cables.

---

## Recommended wiring — J21 tap (no inline shunt)

The INA219 **does not** go in the 12 V power path. It only senses the differential
voltage across J21. Power the board normally through **J20**.

```text
12 V adapter (+) ──────────────────────────────► J20 barrel (+)
12 V adapter (−) ──────────────────────────────► ZedBoard GND  (J3/J4 or header GND)

On-board (already wired):  J20 ──► [10 mΩ] ──► board regulators / load
                                    │
                                 J21 (2 pins)
                                    │
                         INA219 Vin+ / Vin−  (differential sense only)

Pi / USB-I2C:  3.3V, GND, SDA, SCL → INA219
               Pi GND ───────────────► ZedBoard GND  (shared reference)
```

| From | To |
|------|-----|
| J21 pin 1 | INA219 **Vin+** |
| J21 pin 2 | INA219 **Vin−** |
| ZedBoard GND (J3, J4, or header) | INA219 **GND** + Pi **GND** |
| Pi 3.3V / SDA / SCL | INA219 VCC / SDA / SCL |

If current reads negative, swap Vin+ and Vin−. Do **not** power the ZedBoard until
I²C + J21 sense wires are checked.

**Shunt value for software (critical):**

```bash
export INA219_SHUNT_MOHM=10    # ZedBoard on-board 10 mΩ at J21
export INA219_V_RAIL=12.0
```

Using `100` (Adafruit inline shunt) with J21 makes all currents **10× too low**.

---

## Fallback — inline through INA219 (only if J21 unavailable)

Break the **12 V positive** lead and route it through the Adafruit breakout’s **Vin+ → Vin−**
(uses the breakout’s built-in **0.1 Ω = 100 mΩ** shunt):

```text
12V (+) ──► INA219 Vin+ ──► INA219 Vin− ──► J20 barrel (+)
12V (−) ─────────────────────────────────► ZedBoard GND
```

```bash
export INA219_SHUNT_MOHM=100   # Adafruit breakout shunt only (inline method)
```

---

## Raspberry Pi + INA219 (recommended if you have a Pi)

Use the Pi as the **I²C host** for INA219. The **ZedBoard bench still runs on Ubuntu**
(`bsp-lab`) over JTAG — two machines, coordinated by hand.

### Pi → INA219 I²C (3.3 V)

| Pi pin (BCM) | Physical pin | INA219 |
|--------------|--------------|--------|
| 3.3V | 1 | VCC |
| GND | 6 | GND |
| GPIO2 (SDA) | 3 | SDA |
| GPIO3 (SCL) | 5 | SCL |

### Enable I²C on the Pi (once)

```bash
sudo raspi-config          # Interface Options → I2C → Enable → reboot
sudo apt install -y python3-pip i2c-tools git
pip3 install smbus2
sudo usermod -aG i2c $USER   # log out and back in

git clone https://github.com/harsha240yeager/1024-HDC.git ~/1024-HDC
cd ~/1024-HDC && git pull

# Verify INA219 @ 0x40
i2cdetect -y 1
bash scripts/energy_preflight.sh   # must PASS
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

**Terminal B — Raspberry Pi** — run logger:

```bash
cd ~/1024-HDC
pip3 install smbus2

export INA219_BUS=1
export INA219_SHUNT_MOHM=10    # J21 on-board shunt
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

---

## Procedure

1. **Static power:** Program bitstream, hold HDC idle, sample INA219 ~10 s → `P_static`.
2. **Dynamic batch:** Run `run_phase3_bench_load.sh` while logging ~30 s at ~100 Hz.
3. **Integration:** `E_dynamic = ∫ (P_total − P_static) dt`; `E_per_window = E_dynamic / 200`.
4. **Repeat 3×** for mean ± std.

---

## Software

| Script | Role |
|--------|------|
| `scripts/ina219_log.py` | I²C sampler + integration |
| `scripts/run_energy_log_pi.sh` | Pi logger (bench on Ubuntu) |
| `scripts/run_energy_measure.sh` | Ubuntu all-in-one (USB-I2C) |
| `scripts/energy_preflight.sh` | Verify INA219 @ 0x40 |
| `board/HDC_DMA/run_phase3_program_pl.sh` | Program PL only |
| `board/HDC_DMA/run_phase3_bench_load.sh` | Bench ELF reload only |

Default shunt: **10 mΩ** (J21). Use `INA219_SHUNT_MOHM=100` only for inline Adafruit fallback.

---

## Safety

- Verify INA219 + J21 wiring **before** applying 12 V at J20.
- J21 is a **sense tap** — do not drive high current through those pins.
- Share GND between Pi, INA219, and ZedBoard.
