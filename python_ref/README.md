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

## Files

| File | Purpose |
|---|---|
| `hdc_ref.py` | Core library |
| `generate_vectors.py` | Export hex vectors for co-simulation |
| `run_smoke_test.py` | Local regression without pytest |
| `vectors/` | Generated co-sim files (created on demand) |
