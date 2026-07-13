# Twist 1 — silicon informed vs random @ keep=0.125 (128 bits)

Generated: 2026-07-13 (ZedBoard Phase 3 EMG replay, 658,004 windows)

| Condition | Board accuracy | Export ref | PASS |
|-----------|----------------|------------|------|
| Fisher informed (anchor C, pooled) | **74.32%** | 74.32% | ✅ (reused 2026-07-04 run) |
| Random iso-density (seed 0, pooled) | **63.41%** | 63.41% | ✅ Δ0.00% |

**Gap (informed − random): +10.91 pp** on measured ZedBoard replay.

Headline: at identical 128-bit density, **Fisher-informed bit selection preserves accuracy on silicon** while a uniform random mask collapses — matching the Twist 1 Python trend (+8.6 pp per-subject mean @ keep=0.125).

## Evidence

- Informed: [`informed_anchor_C/board_emg_replay.txt`](informed_anchor_C/board_emg_replay.txt) (copy of anchor C)
- Random seed 0: [`random_seed_0/board_emg_replay.txt`](random_seed_0/board_emg_replay.txt)
- Full log: [`full_run.log`](full_run.log)

## Regenerate

```bash
bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0
```
