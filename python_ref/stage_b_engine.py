"""
Stage B BSC spatial encoder — HDC-2 split + masked Hamming classification.

Wraps ``repro/stage_b_bsc.py`` (4-channel bind records, thresholded majority)
for Twist 1 / encoder-ablation work under Protocol HDC-2.

Spatial record per sample: R = majority_c( iM[c] XOR CiM[v_c] )
Classify: argmin masked Hamming(R, P_k)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np
import scipy.io as sio

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "repro"))
sys.path.insert(0, str(REPO / "scripts"))

from repro.stage_b_bsc import (  # noqa: E402
    N_CLASSES as N_CLASS,
    build_bind_tables,
    init_item_memories,
    majority,
    quantize,
    records_for,
)
from export_emg_board_vectors import (  # noqa: E402
    DATASET,
    split_kwargs_from_config,
    split_train_test,
)


@dataclass(frozen=True)
class StageBConfig:
    D: int = 1024
    item_mem_seed: int = 1


class StageBEngine:
    """Stage B spatial-record encoder with masked nearest-prototype search."""

    def __init__(self, cfg: StageBConfig, *, item_mem_seed: Optional[int] = None) -> None:
        self.cfg = cfg
        seed = cfg.item_mem_seed if item_mem_seed is None else item_mem_seed
        rng = np.random.default_rng(seed)
        ci_m, i_m = init_item_memories(cfg.D, rng)
        self.bind_tables = build_bind_tables(ci_m, i_m)

    def encode_quantized(self, q: np.ndarray) -> np.ndarray:
        """Encode level-quantized samples (n, 4) -> hypervectors (n, D)."""
        return records_for(self.bind_tables, q)

    def train_prototypes(self, train_hvs: np.ndarray, train_labels: np.ndarray) -> np.ndarray:
        """Majority bundle per class; returns (N_CLASS, D) rows indexed 0..N_CLASS-1."""
        protos = np.zeros((N_CLASS, self.cfg.D), dtype=np.uint8)
        for k in range(1, N_CLASS + 1):
            sel = train_hvs[train_labels == k]
            if sel.shape[0]:
                protos[k - 1] = majority(sel.sum(0), sel.shape[0])
        return protos

    @staticmethod
    def hamming_masked(hv: np.ndarray, proto: np.ndarray, mask: np.ndarray) -> int:
        return int(((hv ^ proto) & mask).sum())

    def classify(self, hv: np.ndarray, protos: np.ndarray, mask: np.ndarray) -> int:
        """Return 0-indexed class id (matches hdc_ref HDCEngine.classify)."""
        dists = np.array(
            [self.hamming_masked(hv, protos[k], mask) for k in range(protos.shape[0])],
            dtype=np.int32,
        )
        return int(dists.argmin())

    def classify_batch(
        self,
        hvs: np.ndarray,
        protos: np.ndarray,
        mask: np.ndarray,
        *,
        progress_label: str = "",
    ) -> np.ndarray:
        n = hvs.shape[0]
        step = max(1, n // 20)
        preds = np.zeros(n, dtype=np.int32)
        for i in range(n):
            if progress_label and i > 0 and i % step == 0:
                print(f"      classify {progress_label}: {i}/{n}", flush=True)
            preds[i] = self.classify(hvs[i], protos, mask)
        return preds


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_subject_windows(
    subject: int,
    dataset_path: Path,
) -> Tuple[np.ndarray, np.ndarray]:
    mat = sio.loadmat(str(dataset_path))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    return quantize(data), labels


def split_subject_hdc2(
    subject: int,
    *,
    seed: int,
    train_frac: float,
    split_kw: dict,
    dataset_path: Path = DATASET,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    q_all, labels = load_subject_windows(subject, dataset_path)
    return split_train_test(q_all, labels, train_frac, seed, **split_kw)


def accuracy_with_mask(
    engine: StageBEngine,
    queries: np.ndarray,
    labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
    *,
    progress_label: str = "",
) -> Tuple[float, int, int]:
    gt = labels.astype(np.int32) - 1
    preds = engine.classify_batch(queries, protos, mask, progress_label=progress_label)
    correct = int((preds == gt).sum())
    total = int(labels.shape[0])
    return (correct / total if total else 0.0), correct, total


def eval_subject(
    subject: int,
    *,
    seed: int,
    train_frac: float,
    split_kw: dict,
    item_mem_seed: int,
    D: int = 1024,
    dataset_path: Path = DATASET,
    mask: Optional[np.ndarray] = None,
    progress: bool = True,
) -> dict:
    train_q, train_labels, test_q, test_labels = split_subject_hdc2(
        subject,
        seed=seed,
        train_frac=train_frac,
        split_kw=split_kw,
        dataset_path=dataset_path,
    )
    cfg = StageBConfig(D=D, item_mem_seed=item_mem_seed)
    engine = StageBEngine(cfg)

    if progress:
        print(
            f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}",
            flush=True,
        )

    train_hvs = engine.encode_quantized(train_q)
    test_hvs = engine.encode_quantized(test_q)
    protos = engine.train_prototypes(train_hvs, train_labels)

    if mask is None:
        mask = np.ones(D, dtype=np.uint8)

    label = f"s{subject}/test" if progress else ""
    acc, correct, n_test = accuracy_with_mask(
        engine,
        test_hvs,
        test_labels,
        protos,
        mask,
        progress_label=label,
    )

    return {
        "subject": subject,
        "n_train": int(train_q.shape[0]),
        "n_test": n_test,
        "correct": correct,
        "accuracy": acc,
        "train_hvs": train_hvs,
        "train_labels": train_labels,
        "test_hvs": test_hvs,
        "test_labels": test_labels,
        "protos": protos,
    }


def split_config_from_emg(emg_cfg: dict) -> Tuple[int, float, dict, Sequence[int]]:
    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    split_kw = split_kwargs_from_config(emg_cfg)
    subjects = list(emg_cfg["dataset"]["subjects"])
    return seed, train_frac, split_kw, subjects
