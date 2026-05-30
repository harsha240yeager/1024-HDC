#!/usr/bin/env python3
"""Local smoke tests for hdc_ref (no pytest required)."""

from __future__ import annotations

import sys

import numpy as np

from hdc_ref import (
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bind,
    bundle_majority,
    bundle_threshold,
    cross_subject_mask_experiment,
    hamming,
    make_pruning_masks,
    permute,
    self_check_permute_modes,
    train_class_hypervectors,
)


def check(name: str, cond: bool) -> None:
    if not cond:
        raise AssertionError(name)
    print(f"  OK  {name}")


def main() -> int:
    cfg = HDCConfig(D=1024, seed=42)
    engine = HDCEngine(cfg)
    rng = np.random.default_rng(7)

    print("[1/6] permute vs tb_xor_permute golden")
    self_check_permute_modes(cfg, trials=100, seed=99)

    print("[2/6] bundle threshold matches RTL (n_accum >> 1)")
    counts = np.array([9, 10, 11, 0], dtype=np.int32)
    out = bundle_threshold(counts, n_accum=20)
    check("threshold 10 -> 1", out[1] == 1)
    check("threshold 9 -> 0", out[0] == 0)

    print("[3/6] bind + permute pipeline")
    a = rng.integers(0, 2, cfg.D, dtype=np.uint8)
    b = rng.integers(0, 2, cfg.D, dtype=np.uint8)
    y = engine.bind_permute(a, b, perm_mode=2, perm_param=73)
    check("output shape", y.shape == (cfg.D,))

    print("[4/6] EMG record encoding + classify")
    mem = ItemMemory(cfg)
    q = rng.integers(0, cfg.n_levels, size=(cfg.n_channels, cfg.n_features), dtype=np.int32)
    hv = engine.encode_emg_window(q, mem)

    n_train = 40
    train_q = np.stack(
        [
            engine.encode_emg_window(
                rng.integers(0, cfg.n_levels, size=(cfg.n_channels, cfg.n_features)),
                mem,
            )
            for _ in range(n_train)
        ],
        axis=0,
    )
    train_y = rng.integers(0, 5, size=n_train, dtype=np.int32)
    class_hvs = train_class_hypervectors(train_q, train_y, cfg)
    pred = engine.classify(hv, class_hvs)
    check("class id in range", 0 <= pred.class_id < 5)

    print("[5/6] Twist 1 informed vs random masks")
    informed, random_m = make_pruning_masks(train_q, train_y, keep_ratio=0.5, cfg=cfg, random_seed=0)
    check("same density", int(informed.sum()) == int(random_m.sum()))
    check("masks differ", not np.array_equal(informed, random_m))

    print("[6/6] Twist 2 cross-subject experiment (synthetic subjects)")
    subjects = np.repeat(np.arange(8), 5)
    result = cross_subject_mask_experiment(
        train_q[:40],
        train_y[:40],
        subjects[:40],
        cfg,
        keep_ratio=0.5,
        train_subjects=[0, 1, 2, 3],
        random_seed=1,
    )
    check("pooled accuracy is float", 0.0 <= result["accuracy_pooled_informed"] <= 1.0)

    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
