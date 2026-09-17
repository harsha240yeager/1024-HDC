# Anchor A on narrow PL — not applicable

The H1 narrow bitstream (Option E) bakes **K=128** Fisher gather for **keep=0.125 (anchor C)** only. It cannot replay anchor A (keep=1.0, D=1024) without a different SEL table / resynthesis.

**Paper #31 accuracy row:** use baseline PL EMG replay:

- `results/protocol_v2/anchors/anchor_A/board_emg_replay.txt` — **72.78%** (493,512 windows, PASS vs export)
