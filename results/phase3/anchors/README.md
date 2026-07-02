# Phase 3 — Hook A on-board anchor replays

Reprogram the **global pruning mask** (`emg_mask64`) and replay full EMG on silicon.
Same Phase 3 bitstream; levels/protos/DDR bin unchanged.

| Anchor | keep | Prune | Hook A Python target |
|--------|------|-------|----------------------|
| A | 1.0 | 0% | ~74.15% |
| B | 0.5 | 50% | ~74.15% |
| C | 0.125 | 87.5% | ~74.15% |

## Mask consistency (silicon vs Hook A Python)

| Anchor | Silicon mask | Hook A sweep mask | Same bits? |
|--------|--------------|-------------------|------------|
| **A** | keep=1.0 → **full mask** (Fisher scores not computed) | per-subject Fisher @ keep=1.0 → all-ones | **Yes** |
| **B, C** | **pooled** Fisher over all subjects' TRAIN windows | **per-subject** Fisher, spatial mean in sweep | **May differ** |

Board PASS is vs **patched export ref** (0.5% tol), not vs Hook A's 74.15% literally.
Original RTL baseline replay remains **74.24%** — see [two-baseline story](../../../README.md#accuracy-the-two-baseline-story).

## Run

```bash
cd ~/1024-HDC
bash board/HDC_DMA/run_anchor_replay.sh A    # baseline (keep=1.0, full mask)
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
