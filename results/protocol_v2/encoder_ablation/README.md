# Issue 6 - Path B encoder ablation (Stage B -> RTL)

Generated: 2026-07-25T10:55:58Z
Protocol: **HDC-2** · D=1024 · subjects=[1, 2, 3, 4, 5]

Path A (BSC in PL) is **out of scope**. This table explains the ~17 pp gap
between the literature BSC reference and the deployed RTL encoder.

## Spatial mean

| Step | Configuration | Test set | Acc | Δ vs prev (pp) |
|------|---------------|----------|-----|----------------|
| `stage_b_literature_fulltest` | Stage B BSC (literature protocol) | full_recording | **90.17%** | - |
| `stage_b_hdc2` | Stage B BSC @ HDC-2 | disjoint | **89.37%** | -0.80 |
| `stage_b_hdc2_seed42` | Stage B + item-mem seed 42 | disjoint | **90.82%** | +1.45 |
| `stage_b_hdc2_16levels` | Stage B + 16-level CiM | disjoint | **90.26%** | -0.56 |
| `rtl_4bind` | RTL item mem + 4 binds | disjoint | **73.28%** | -16.98 |
| `rtl_20bind` | RTL encoder (20 binds) | disjoint | **72.89%** | -0.39 |

## What moves the needle

- **Protocol / seed / 21→16 levels:** small (±1–2 pp).
- **Stage-B `iM⊕CiM` records → RTL item memory + Eq. 3.1 bind (4 channels):**
  **−17.0 pp** (90.26% → 73.28%) — the dominant gap.
- **4 → 20 binds (feature grid):** only **−0.4 pp** (73.28% → 72.89%).

So the literature↔deployment gap is mostly the **encoding/item-memory model**,
not the extra feature slots.

## Encoder redundancy — `level21_to_grid` (issue #25)

### What the export grid does

Each EMG window is one time sample with **four** quantized envelope channels
(0–21). The RTL encoder expects a **4×5** grid of level indices (20 slots). The
mapping function replicates each channel's level across all five feature columns:

```89:97:scripts/export_emg_board_vectors.py
def level21_to_grid(sample_q4: np.ndarray, cfg: HDCConfig) -> np.ndarray:
    grid = np.zeros((cfg.n_channels, cfg.n_features), dtype=np.int32)
    for c in range(cfg.n_channels):
        lvl21 = int(np.clip(int(sample_q4[c]), 0, EMG_MAXL))
        lvl16 = int(round(lvl21 * (cfg.n_levels - 1) / EMG_MAXL))
        lvl16 = int(np.clip(lvl16, 0, cfg.n_levels - 1))
        for f in range(cfg.n_features):
            grid[c, f] = lvl16
    return grid
```

**Effect:** per window there are only **four distinct level values** (one per
channel). The five "feature" slots are **redundant copies** — they carry no
additional information beyond the channel envelope. The encoder is effectively a
**4-record spatial encoder** routed through a 20-bind majority bundle.

Rescaling: envelope **0–21** → value item memory **16 levels** (`round(lvl21 × 15/21)`).

### Ablation evidence (20 binds ≈ 4 binds)

| Configuration | Binds | Spatial mean | Δ vs 4-bind |
|---------------|-------|--------------|-------------|
| `rtl_4bind` | 4 (one per channel, feature index 0) | **73.28%** | — |
| `rtl_20bind` | 20 (full grid, deployed path) | **72.89%** | **−0.39 pp** |

The 20-bind path uses `encode_emg_window(grid, …)` (full permute-and-bundle);
4-bind uses one `encode_record_pair(c, 0, level)` per channel then majority.
Both call **`level21_to_grid` first**, so the redundant grid explains why accuracy
is unchanged: repeating the same level five times does not add entropy.

This is **not** the cause of sparse active support (~209 bits) — independent
per-slot levels give similar support ([`active_support_mechanism/`](../active_support_mechanism/)).

### Pipeline consistency (Python ≡ board)

**Single source of truth:** `scripts/export_emg_board_vectors.py::level21_to_grid`

All hdc_ref Python sweeps and silicon export import this function (not reimplemented):

| Consumer | Role |
|----------|------|
| `scripts/export_emg_board_vectors.py` | Board vector export + on-board replay golden |
| `scripts/export_fisher_pooled.py` | Pooled Fisher masks for silicon anchors |
| `scripts/patch_emg_anchor.py` | Anchor bitstream patching |
| `scripts/twist2_mask_audit_fast.py` | Cross-subject mask audit |
| `python_ref/run_hook_a_sweep.py` | Hook A design-space sweep |
| `python_ref/run_twist1_sweep.py` | Twist 1 iso-density |
| `python_ref/run_twist2_sweep.py` | Twist 2 cross-subject |
| `python_ref/run_ranking_baselines.py` | Issue #9 ranking baselines |
| `python_ref/run_seed_sensitivity.py` | Item-memory seed sensitivity |
| `python_ref/run_active_bit_ablation.py` | Active-bit / support ablation |
| `python_ref/run_encoder_ablation.py` | This ladder (4 vs 20 binds) |
| `python_ref/run_arm_hdc_baseline.py` | ARM host parity check |

**Stage B** (`stage_b_bsc`) uses a different encoder (4-channel records, no
20-bind grid) — see [`twist1_stage_b/`](../twist1_stage_b/) for dense-support falsification.

### FAQ (advisor / reviewer)

**What are your five features?** Five **slots** in the bind grid, not five
independent Hudgins-style features. Each channel's envelope level is copied to
all five columns; only four values vary per window.

**Why keep 20 binds in RTL?** (1) Costs ~0.4 pp vs 4 binds. (2) Exercises the
full permute-and-bundle datapath frozen for bit-exact silicon. (3) Changing the
grid now would invalidate the export reference and anchor bitstreams.

**Is Python inconsistent with the board?** No — same `level21_to_grid`, same
item-memory seed (42 for deployment), same 16-level value table.

**21 levels or 16?** Both: dataset quantization 0–21; RTL indexes a 16-entry
value ROM (4-bit codes, 80-bit packed window).

### Paper text (draft for integration #36)

> The export path maps each channel's 0–21 envelope level onto the 16-entry value
> item memory and replicates it across all five feature slots (`level21_to_grid`),
> so the deployed encoder uses four distinct levels per window despite a 4×5 bind
> grid; encoder ablation shows 20 binds (72.89%) ≈ 4 binds (73.28%).

Optional follow-up: real per-feature encoding tracked as [#34](https://github.com/harsha240yeager/1024-HDC/issues/34).

## Regenerate

```bash
python3 python_ref/run_encoder_ablation.py --quick
python3 python_ref/run_encoder_ablation.py
```
