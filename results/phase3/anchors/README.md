# Phase 3 — Hook A on-board anchor replays

Reprogram the **global pruning mask** (`emg_mask64`) and replay full EMG on silicon.
Same Phase 3 bitstream; levels/protos/DDR bin unchanged.

| Anchor | keep | Prune | Python target |
|--------|------|-------|----------------|
| A | 1.0 | 0% | ~74.15% |
| B | 0.5 | 50% | ~74.15% |
| C | 0.125 | 87.5% | ~74.15% |

Mask: **pooled Fisher-informed** over all subjects' TRAIN windows (one mask for full replay).

## Run

```bash
cd ~/1024-HDC
bash board/HDC_DMA/run_anchor_replay.sh A    # baseline (keep=1.0)
bash board/HDC_DMA/run_anchor_replay.sh B    # knee
bash board/HDC_DMA/run_anchor_replay.sh C    # aggressive
bash board/HDC_DMA/run_anchor_replay.sh ALL  # sequential A → B → C
```

Outputs:

- `anchors/anchor_A/board_emg_replay.txt`
- `anchors/anchor_B/board_emg_replay.txt`
- `anchors/anchor_C/board_emg_replay.txt`

Pass: board accuracy within **0.5%** of patched export ref (same gate as main EMG replay).

## Manual steps

```bash
python3 scripts/patch_emg_anchor.py --anchor B
# rebuild EMG ELF + run_phase3_emg.sh (see run_anchor_replay.sh)
```

Patch only (no accuracy recompute — dev):

```bash
python3 scripts/patch_emg_anchor.py --anchor B --skip-accuracy
```
