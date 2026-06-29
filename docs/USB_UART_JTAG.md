# USB UART + JTAG on ZedBoard (1024-HDC)

The ZedBoard **PROG/UART** micro-USB cable carries **both** JTAG (programming,
DDR load, result poll) and **PS UART** (115200 serial) on one FTDI FT2232 chip.
They can run together, but heavy JTAG transfers can stall UART for a while.

This guide is the fix for “USB logs not showing while JTAG runs.”

---

## What changed in firmware (EMG replay)

`sw/hdc_emg_board_test.c` now prints **live progress** on UART and mirrors the
same partial counts to **DDR @ 0x00100300** so JTAG polling and serial stay in sync:

- Startup banner before inference
- Per-subject start / done lines
- Every **2000 windows** (10 × 200-window DMA batches):  
  `progress: N / total  correct=…  acc=…%`
- Final PASS/FAIL summary (unchanged)

Rebuild after pulling:

```bash
cd ~/1024-HDC/board/HDC_DMA
export HDC_VIVADO_ROOT=/path/to/FInal_HDC
bash build_sw.sh
```

---

## Two-terminal workflow (recommended on the board)

### Terminal A — UART (open **first**)

```bash
# Find the serial port (Digilent UART is usually ttyUSB0; if empty try ttyUSB1)
ls -la /dev/serial/by-id/*Digilent* 2>/dev/null
ls -la /dev/ttyUSB*

picocom -b 115200 /dev/ttyUSB0
# Exit picocom: Ctrl+A then Ctrl+X
```

Settings: **115200, 8N1, no hardware flow control**.

Leave this terminal open for the whole run.

### Terminal B — JTAG program + poll

```bash
cd ~/1024-HDC/board/HDC_DMA
export HDC_VIVADO_ROOT=/path/to/FInal_HDC

# Kill stale sessions (required if a prior run failed)
pkill -f 'hw_server.*3121' 2>/dev/null
pkill -f rdi_xsdb 2>/dev/null
pkill minicom 2>/dev/null
sleep 2

bash run_phase3_emg.sh 2>&1 | tee /tmp/emg_run.log
```

Official PASS/FAIL is still written to `results/phase3/board_emg_replay.txt`.

---

## What to expect on each terminal

| Phase | UART (Terminal A) | JTAG log (Terminal B) |
|-------|-------------------|------------------------|
| PL bitstream program | Often silent / frozen | `PL programmed successfully` |
| Load `emg_board_vectors.bin` (~11 MB) | **Often frozen 5–15 min** | `usb bulk read failed` on some chunks is OK if retries continue |
| EMG inference (658k windows) | **Live `progress:` lines** every ~2000 windows | `n=… correct=…` every ~10 s |
| Done | Final `EMG replay: … PASS` block | Same summary from DDR readback |

During the **vector load**, UART may not update — that is normal. Once you see
`CPU running EMG replay` in the JTAG log, UART progress should resume.

---

## Checklist — fix USB log problems

1. **Board power** on, **JP7 = JTAG**, PROG/UART USB plugged (not OTG).
2. **Cable detected:**
   ```bash
   lsusb | grep 0403:6014
   ls -la /dev/ttyUSB0
   ```
3. **User in `dialout` group** (logout/login after adding):
   ```bash
   groups | grep dialout
   ```
4. **Close conflicting tools:** Vivado Hardware Manager, Vitis debug, minicom in
   the same session you use for JTAG (picocom in a *separate* terminal is fine).
5. **Open UART before JTAG** (Terminal A then B).
6. **Direct motherboard USB port** — avoid hubs during the 11 MB DDR load.
7. **If FTDI errors:** unplug USB 5 s, replug, power-cycle board, retry:
   ```bash
   pkill -f hw_server; sleep 3
   bash run_phase3_emg.sh
   ```
8. **Rebuild EMG ELF** after pulling progress-print changes (`build_sw.sh`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No `/dev/ttyUSB0` | Check USB cable, power, `lsusb`; try another port |
| Garbled text | Wrong baud (use 115200) or JTAG load still running — wait |
| UART empty entire run | Old ELF without progress prints — rebuild; or wrong tty device |
| `usb bulk read failed` | Retry; load often completes despite errors (see log for `Vectors bin loaded`) |
| `Close minicom first` | Exit picocom **in the JTAG terminal’s conflict check** only affects minicom blocking hw_server setup — use picocom in a separate terminal, not minicom during `run_phase3_emg.sh` startup |
| PASS only on JTAG, not UART | UART is for monitoring; **JTAG DDR readback is authoritative** |

---

## Short test (UART + JTAG, low stress)

```bash
# Terminal A
picocom -b 115200 /dev/ttyUSB0

# Terminal B
cd ~/1024-HDC/board/HDC_DMA
bash run_phase3_bench.sh
```

Bench finishes in seconds — good sanity check before the 658k-window EMG run.

---

## Optional: second USB-serial adapter

For completely independent debug during heavy JTAG loads, wire a **USB-UART
adapter** to a PMOD pinout on a spare PS UART (requires BD/pin changes). The
on-board PROG/UART port cannot be split into two physical cables.

---

## Related files

| File | Role |
|------|------|
| `sw/hdc_emg_board_test.c` | UART progress + DDR status block |
| `board/HDC_DMA/run_phase3_emg.sh` | One-command EMG board run |
| `board/HDC_DMA/_ide/run_emg_all.tcl` | JTAG program + DDR poll |
| `board/HDC_DMA/_ide/common.sh` | hw_server / Digilent USB helpers |
| `results/phase3/board_emg_replay.txt` | Recorded PASS/FAIL |
