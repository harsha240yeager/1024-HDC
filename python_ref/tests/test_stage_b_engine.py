#!/usr/bin/env python3
"""Unit tests for Stage B engine (Phase 1 masked path)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "repro"))

from hdc_ref import mask_from_scores, per_bit_fisher_scores  # noqa: E402
from stage_b_engine import StageBConfig, StageBEngine, accuracy_with_mask  # noqa: E402


class StageBEngineTests(unittest.TestCase):
    def test_full_mask_classify(self) -> None:
        rng = np.random.default_rng(0)
        cfg = StageBConfig(D=256, item_mem_seed=1)
        engine = StageBEngine(cfg)
        q = rng.integers(0, 22, size=(40, 4), dtype=np.int64)
        labels = rng.integers(1, 6, size=40, dtype=np.int64)
        hvs = engine.encode_quantized(q)
        protos = engine.train_prototypes(hvs, labels)
        full = np.ones(cfg.D, dtype=np.uint8)
        acc, _, _ = accuracy_with_mask(engine, hvs, labels, protos, full)
        self.assertGreater(acc, 0.0)

    def test_masked_vs_full_when_lossless(self) -> None:
        rng = np.random.default_rng(1)
        cfg = StageBConfig(D=256, item_mem_seed=7)
        engine = StageBEngine(cfg)
        q = rng.integers(0, 22, size=(60, 4), dtype=np.int64)
        labels = rng.integers(1, 6, size=60, dtype=np.int64)
        hvs = engine.encode_quantized(q)
        protos = engine.train_prototypes(hvs, labels)
        scores = per_bit_fisher_scores(hvs, labels.astype(np.int32))
        full = np.ones(cfg.D, dtype=np.uint8)
        keep_mask = mask_from_scores(scores, 1.0, informed=True)
        acc_full, _, _ = accuracy_with_mask(engine, hvs, labels, protos, full)
        acc_keep, _, _ = accuracy_with_mask(engine, hvs, labels, protos, keep_mask)
        self.assertAlmostEqual(acc_full, acc_keep, places=9)

    def test_hamming_masked_subset(self) -> None:
        hv = np.array([1, 0, 1, 0], dtype=np.uint8)
        proto = np.array([1, 1, 0, 0], dtype=np.uint8)
        mask = np.array([1, 0, 1, 1], dtype=np.uint8)
        self.assertEqual(StageBEngine.hamming_masked(hv, proto, mask), 1)


if __name__ == "__main__":
    unittest.main()
