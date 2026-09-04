# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)

HDC-2 cohort: **493,512** windows (5 subjects, pooled random mask).

## Informed baseline (silicon measured)

| Condition | Board accuracy | Export ref | PASS |
|-----------|----------------|------------|------|
| Fisher informed (anchor C, pooled) | **72.84%** | 72.85% | ✅ (reuse `protocol_v2/anchors/anchor_C/`) |

Evidence: [`informed_anchor_C/board_emg_replay.txt`](informed_anchor_C/board_emg_replay.txt)

## Random masks — export ref vs board

**Export ref** = Python `hdc_ref` replay over the same frozen window bin (`scripts/patch_emg_anchor.py`).
**Board** = measured ZedBoard JTAG replay (`board_emg_replay.txt`). PASS when |board − export| ≤ 0.5%.

| Seed | Export ref (predicted) | Gap vs informed | Board (measured) | Board gap | Board PASS |
|------|------------------------|-----------------|------------------|-----------|------------|
| 0 | 62.51% | +10.33 pp | **62.51%** | +10.33 pp | ✅ Δ0.00% |
| 1 | 64.58% | +8.26 pp | — | — | ⏳ pending |
| 2 | 67.64% | +5.20 pp | — | — | ⏳ pending |
| 3 | 62.78% | +10.06 pp | — | — | ⏳ pending |
| 4 | 66.00% | +6.84 pp | — | — | ⏳ pending |
| 5 | 61.55% | +11.29 pp | — | — | ⏳ pending |
| 6 | 64.63% | +8.21 pp | — | — | ⏳ pending |
| 7 | 67.57% | +5.27 pp | — | — | ⏳ pending |
| 8 | 69.23% | +3.61 pp | — | — | ⏳ pending |
| 9 | 67.49% | +5.35 pp | — | — | ⏳ pending |

**Export ref summary (seeds 1–9):** mean gap **+7.12 pp** (range +3.61 to +11.29 pp).
**Silicon measured today:** seed 0 only (+10.33 pp). Board sweep for seeds 1–9 pending.

Machine-readable export refs: [`export_ref_predictions.json`](export_ref_predictions.json)

## Evidence (board)

- Random seed 0: [`random_seed_0/board_emg_replay.txt`](random_seed_0/board_emg_replay.txt)
- Success log: [`hdc2_seed0_replay_v2.log`](hdc2_seed0_replay_v2.log)
- Patch notes: [`random_seed_0/patch_status.txt`](random_seed_0/patch_status.txt)

## Regenerate export refs (Python)

```bash
python3 scripts/patch_emg_anchor.py --anchor C --keep-ratio 0.125 \
  --mask-mode random --random-seed N --label twist1_random_sN
```

Full seeds 0–9 batch (no header patch): see [`export_ref_seeds0-9.log`](export_ref_seeds0-9.log).

## Regenerate board replay

```bash
# Seed 0 (mask already patched):
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0 --skip-patch

# Seeds 1–9 (patch + replay each):
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 1,2,3,4,5,6,7,8,9
```

JTAG: if no APU (`DAP 0x30000021`), restart hw_server and retry — see `board/HDC_DMA/_ide/program_board_helpers.tcl` (`recover_apu_chain`).

## Automated seed sweep (seeds 1–9)

```bash
bash scripts/run_silicon_random_seeds.sh --seeds 1-9 --resume
```

Stops on JTAG corruption and writes [`jtag_failure_report.md`](jtag_failure_report.md).
