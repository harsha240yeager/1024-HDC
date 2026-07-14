#!/usr/bin/env python3
"""Unit tests for Protocol HDC-2 disjoint split (no dataset required)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from export_emg_board_vectors import (  # noqa: E402
    compute_test_indices,
    compute_train_indices,
    protocol_test_set,
    split_train_test,
)


def test_disjoint_no_overlap() -> None:
    labels = np.concatenate([np.full(200, c, dtype=np.int64) for c in range(1, 6)])
    q = np.zeros((labels.size, 4), dtype=np.int64)
    train_idx = compute_train_indices(labels, 0.25, seed=1)
    test_idx = compute_test_indices(labels, train_idx, boundary_gap=0)
    overlap = set(train_idx.tolist()) & set(test_idx.tolist())
    assert not overlap, f"overlap={len(overlap)}"
    _, _, tq, _ = split_train_test(q, labels, 0.25, 1, test_set="disjoint")
    assert tq.shape[0] == test_idx.size


def test_hdc1_full_recording_has_overlap() -> None:
    labels = np.concatenate([np.full(100, c, dtype=np.int64) for c in range(1, 6)])
    q = np.zeros((labels.size, 4), dtype=np.int64)
    train_idx = compute_train_indices(labels, 0.25, seed=1)
    _, _, tq, _ = split_train_test(q, labels, 0.25, 1, test_set="full_recording")
    assert tq.shape[0] == labels.size
    assert len(set(train_idx.tolist()) & set(range(labels.size))) == train_idx.size


def test_protocol_test_set_from_config() -> None:
    hdc1 = {"protocol": {"id": "P-may2026", "test_set": "full per-subject sequence"}}
    hdc2 = {"protocol": {"id": "HDC-2", "test_set": "remaining 75% disjoint"}}
    assert protocol_test_set(hdc1) == "full_recording"
    assert protocol_test_set(hdc2) == "disjoint"


def main() -> int:
    test_disjoint_no_overlap()
    print("  OK  test_disjoint_no_overlap")
    test_hdc1_full_recording_has_overlap()
    print("  OK  test_hdc1_full_recording_has_overlap")
    test_protocol_test_set_from_config()
    print("  OK  test_protocol_test_set_from_config")
    print("All split tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
