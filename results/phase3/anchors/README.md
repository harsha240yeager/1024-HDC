# Phase 3 — Hook A on-board anchor replays

Reprogram the **global pruning mask** (`emg_mask64`) and replay full EMG on silicon.
Same Phase 3 bitstream; levels/protos/DDR bin unchanged.

## Measured results (2026-07-03/04)

Pooled Fisher mask · 658,004 windows · PASS = board within **0.5%** of patched export ref.

| Anchor | keep | Prune | Board acc | Export ref | Δ | Log |
|--------|------|-------|-----------|------------|---|-----|
| **A** | 1.0 | 0% | **74.24%** | 74.24% | 0.00% | [`anchor_A/board_emg_replay.txt`](anchor_A/board_emg_replay.txt) |
| **B** | 0.5 | 50% | **74.24%** | 74.24% | 0.00% | [`anchor_B/board_emg_replay.txt`](anchor_B/board_emg_replay.txt) |
| **C** | 0.125 | 87.5% | **74.32%** | 74.32% | 0.00% | [`anchor_C/board_emg_replay.txt`](anchor_C/board_emg_replay.txt) |

Accuracy is **flat across prune levels** (expected with informed Fisher at D=1024; matches Hook A Python).
Energy at J21 was flat ~12 µJ/w at A/B/C — see [`../energy_summary.txt`](../energy_summary.txt).

## Mask consistency (silicon vs Hook A Python)

| Anchor | Silicon mask | Hook A sweep mask | Same bits? |
|--------|--------------|-------------------|------------|
| **A** | keep=1.0 → **full mask** (Fisher scores not computed) | per-subject Fisher @ keep=1.0 → all-ones | **Yes** |
| **B, C** | **pooled** Fisher over all subjects' TRAIN windows | **per-subject** Fisher, spatial mean in sweep | **May differ** |

Board PASS is vs **patched export ref**, not vs Hook A's 74.15% Python mean alone.

## Run

```bash
cd ~/1024-HDC
bash board/HDC_DMA/run_anchor_replay.sh A    # baseline (keep=1.0, full mask)
bash board/HDC_DMA/run_anchor_replay.sh B    # knee
bash board/HDC_DMA/run_anchor_replay.sh C    # aggressive
bash board/HDC_DMA/run_anchor_replay.sh ALL  # sequential A → B → C
```

Resume board only after patch (skip ~2 h recompute):

```bash
HDC_ANCHOR_SKIP_PATCH=1 bash board/HDC_DMA/run_anchor_replay.sh B
```

## Manual patch

```bash
python3 scripts/patch_emg_anchor.py --anchor B
# rebuild EMG ELF + run_phase3_emg.sh (see run_anchor_replay.sh)
```
