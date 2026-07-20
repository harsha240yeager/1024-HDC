# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)

Generated: 2026-07-20 (ZedBoard Phase 3 EMG replay, **493,512** HDC-2 windows)

| Condition | Board accuracy | Export ref | PASS |
|-----------|----------------|------------|------|
| Fisher informed (anchor C, pooled) | **72.84%** | 72.85% | ✅ (reuse `protocol_v2/anchors/anchor_C/`) |
| Random iso-density (seed 0, pooled) | **62.51%** | 62.51% | ✅ Δ0.00% |

**Gap (informed − random): +10.33 pp** on measured ZedBoard replay (seed 0 only; seeds 1–9 pending).

## Evidence

- Informed: [`informed_anchor_C/board_emg_replay.txt`](informed_anchor_C/board_emg_replay.txt)
- Random seed 0: [`random_seed_0/board_emg_replay.txt`](random_seed_0/board_emg_replay.txt)
- Success log: [`hdc2_seed0_replay_v2.log`](hdc2_seed0_replay_v2.log)
- Patch notes: [`random_seed_0/patch_status.txt`](random_seed_0/patch_status.txt)

## Regenerate

```bash
# Seed 0 (mask already patched):
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0 --skip-patch

# Seeds 1–9 (patch + replay each):
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 1,2,3,4,5,6,7,8,9
```

JTAG: if no APU (`DAP 0x30000021`), restart hw_server and retry — see `board/HDC_DMA/_ide/program_board_helpers.tcl` (`recover_apu_chain`).
