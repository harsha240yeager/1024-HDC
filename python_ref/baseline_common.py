"""Shared helpers for Tier 4 baseline runners (P-may2026 protocol)."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import scipy.io as sio

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from export_emg_board_vectors import (  # noqa: E402
    DATASET,
    N_CLASS,
    quantize_envelope,
    require_dataset,
    split_train_test,
)

DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline.json"
DEFAULT_BASELINE_CFG = HERE / "config" / "baselines.json"
OUT_DIR = REPO / "results" / "baselines"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_subject_split(
    subject: int,
    seed: int,
    train_frac: float,
    max_test_windows: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)
    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed
    )
    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q = test_q[:max_test_windows]
        test_labels = test_labels[:max_test_windows]
    return train_q, train_labels, test_q, test_labels


def cap_train_windows(
    train_q: np.ndarray,
    train_labels: np.ndarray,
    max_train_windows: Optional[int],
) -> Tuple[np.ndarray, np.ndarray]:
    if max_train_windows is not None and train_q.shape[0] > max_train_windows:
        train_q = train_q[:max_train_windows]
        train_labels = train_labels[:max_train_windows]
    return train_q, train_labels


def spatial_mean_accuracy(per_subject: Sequence[dict]) -> float:
    return float(np.mean([r["accuracy"] for r in per_subject]))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_summary_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "baseline", "spatial_mean_accuracy", "n_subjects",
        "n_params", "notes",
    ]
    write_header = not path.is_file()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for row in rows:
            w.writerow(row)


def baseline_meta(name: str, cfg: dict, extra: Optional[dict] = None) -> dict:
    meta = {
        "generated_at": utc_now(),
        "baseline": name,
        "protocol": cfg.get("protocol", "P-may2026"),
    }
    if extra:
        meta.update(extra)
    return meta
