# HDC Python Golden Reference

Bit-exact reference model for the 1024HDC RTL (`xor_permute_top`, `permute_stage`,
future `bundle_unit`, `popcount_am`, `pruning_mask`).

## Setup

```powershell
cd C:\Modelsim_projects\1024HDC\python_ref
python -m pip install -r requirements.txt
```

## Quick smoke test

```powershell
python run_smoke_test.py
```

## Generate ModelSim stimulus / expected outputs

```powershell
python generate_vectors.py --out-dir vectors --count 1000 --seed 42
```

## Library usage

```python
from hdc_ref import HDCConfig, HDCEngine, ItemMemory, train_class_hypervectors

cfg = HDCConfig(D=1024, seed=42)
engine = HDCEngine(cfg)
mem = ItemMemory(cfg)

# bind + permute (matches xor_permute_top)
out = engine.bind_permute(in_vec, bind_vec, perm_mode=2, perm_param=73)

# EMG-style record encoding
query = engine.encode_emg_window(quantized_features, mem)

# Twist 1: informed vs random pruning masks
informed, random = engine.make_pruning_masks(query_hvs, labels, keep_ratio=0.5, seed=0)
```

## EMG baselines (dual-track)

Two accuracy numbers under protocol P-may2026 — see `docs/Baseline_vs_RTL_Encoder.md`:

| Track | Script | Spatial @ D=1024 | Role |
|-------|--------|------------------|------|
| Stage B reference | `run_emg_baseline.py` / `repro/stage_b_bsc.py` | **~90.30%** | Python vs Rahimi / literature |
| RTL encoder | `hdc_ref` + board EMG replay | **~74.24%** | Verified deployment path |

```powershell
python run_emg_baseline.py --quick --no-parity
python run_emg_baseline.py --measure-rtl-ref --rtl-max-windows 5000
```

Config: `config/emg_baseline.json` · Results snapshot: `results/emg_baseline.json`

## Files

| File | Purpose |
|---|---|
| `hdc_ref.py` | Core library |
| `generate_vectors.py` | Export hex vectors for co-simulation |
| `run_smoke_test.py` | Local regression without pytest |
| `vectors/` | Generated co-sim files (created on demand) |
