#!/usr/bin/env python3
"""Quick compare Stage B vs hdc_ref spatial accuracy (same protocol)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python_ref"))
sys.path.insert(0, str(REPO / "python_ref" / "repro"))
sys.path.insert(0, str(REPO))

from hdc_ref import HDCConfig  # noqa: E402
from scripts.export_emg_board_vectors import (  # noqa: E402
    DEFAULT_CONFIG,
    evaluate_subject_hdc_ref,
)
from stage_b_bsc import run as stage_b_run  # noqa: E402


def main() -> int:
    cfg_json = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    subjects = cfg_json["dataset"]["subjects"]
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    cfg = HDCConfig(D=1024, seed=42)

    print("=== hdc_ref (RTL encoder path, per-sample) ===")
    accs = []
    for s in subjects:
        r = evaluate_subject_hdc_ref(s, cfg, seed, train_frac, 42, None)
        accs.append(r["accuracy"])
        print(
            f"  S{s}: {r['accuracy'] * 100:.2f}%  "
            f"train={r['n_train']} test={r['n_windows']}"
        )
    print(f"  mean: {np.mean(accs) * 100:.2f}%")

    print("\n=== Stage B spatial (frozen baseline path) ===")
    res = stage_b_run([1024], subjects, "spatial", seed)
    sp = res["spatial"][1024]
    for s in subjects:
        print(f"  S{s}: {sp[s] * 100:.2f}%")
    print(f"  mean: {sp['mean'] * 100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
