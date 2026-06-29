#!/usr/bin/env python3
"""
Tiny int8 MLP baseline on EMG (P-may2026 protocol).

2-layer feedforward (~5k params) on 4-channel envelope samples (normalized).
Same train/test split as Hook A and board replay. Float train + optional int8
inference report for the paper rebuttal baseline.

Usage (repo root):
  python3 python_ref/run_mlp_baseline.py
  python3 python_ref/run_mlp_baseline.py --quick
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

from baseline_common import (  # noqa: E402
    DEFAULT_BASELINE_CFG,
    DEFAULT_EMG_CFG,
    OUT_DIR,
    append_summary_csv,
    baseline_meta,
    load_json,
    load_subject_split,
    spatial_mean_accuracy,
    write_json,
)
from export_emg_board_vectors import require_dataset  # noqa: E402

N_CLASS = 5
LEVELS = 21


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def softmax(x: np.ndarray) -> np.ndarray:
    z = x - x.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def count_params(w1, b1, w2, b2, w3, b3) -> int:
    return int(w1.size + b1.size + w2.size + b2.size + w3.size + b3.size)


def init_mlp(rng: np.random.Generator, in_dim: int, h1: int, h2: int, out_dim: int):
    scale1 = np.sqrt(2.0 / in_dim)
    scale2 = np.sqrt(2.0 / h1)
    scale3 = np.sqrt(2.0 / h2)
    w1 = rng.normal(0, scale1, (in_dim, h1))
    b1 = np.zeros(h1)
    w2 = rng.normal(0, scale2, (h1, h2))
    b2 = np.zeros(h2)
    w3 = rng.normal(0, scale3, (h2, out_dim))
    b3 = np.zeros(out_dim)
    return w1, b1, w2, b2, w3, b3


def forward(
    x: np.ndarray,
    w1, b1, w2, b2, w3, b3,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    z1 = x @ w1 + b1
    a1 = relu(z1)
    z2 = a1 @ w2 + b2
    a2 = relu(z2)
    logits = a2 @ w3 + b3
    return z1, a1, z2, a2, logits


def train_epoch(
    x: np.ndarray,
    y: np.ndarray,
    w1, b1, w2, b2, w3, b3,
    lr: float,
    batch_size: int,
    rng: np.random.Generator,
) -> float:
    n = x.shape[0]
    idx = rng.permutation(n)
    loss_sum = 0.0
    for start in range(0, n, batch_size):
        batch = idx[start : start + batch_size]
        xb = x[batch]
        yb = y[batch]
        z1, a1, z2, a2, logits = forward(xb, w1, b1, w2, b2, w3, b3)
        probs = softmax(logits)
        loss = -np.log(probs[np.arange(len(batch)), yb] + 1e-9).mean()
        loss_sum += loss * len(batch)

        dlogits = probs.copy()
        dlogits[np.arange(len(batch)), yb] -= 1.0
        dlogits /= len(batch)

        dw3 = a2.T @ dlogits
        db3 = dlogits.sum(axis=0)
        da2 = dlogits @ w3.T
        dz2 = da2 * (z2 > 0)
        dw2 = a1.T @ dz2
        db2 = dz2.sum(axis=0)
        da1 = dz2 @ w2.T
        dz1 = da1 * (z1 > 0)
        dw1 = xb.T @ dz1
        db1 = dz1.sum(axis=0)

        w1 -= lr * dw1
        b1 -= lr * db1
        w2 -= lr * dw2
        b2 -= lr * db2
        w3 -= lr * dw3
        b3 -= lr * db3

    return loss_sum / n


def quantize_affine(w: np.ndarray) -> Tuple[np.ndarray, float, int]:
    """Symmetric int8 per weight tensor."""
    scale = float(np.max(np.abs(w)) / 127.0) if w.size else 1.0
    if scale < 1e-9:
        scale = 1.0
    qw = np.clip(np.round(w / scale), -127, 127).astype(np.int8)
    return qw, scale, 0


def int8_linear(x: np.ndarray, qw: np.ndarray, scale: float, bias: np.ndarray) -> np.ndarray:
    return (x @ (qw.astype(np.float32) * scale)) + bias


def predict_int8(x: np.ndarray, layers) -> np.ndarray:
    (qw1, s1, b1), (qw2, s2, b2), (qw3, s3, b3) = layers
    h1 = relu(int8_linear(x, qw1, s1, b1))
    h2 = relu(int8_linear(h1, qw2, s2, b2))
    logits = int8_linear(h2, qw3, s3, b3)
    return logits.argmax(axis=1)


def featurize(q: np.ndarray) -> np.ndarray:
    return (q.astype(np.float32) / float(LEVELS - 1)).clip(0.0, 1.0)


def evaluate_subject(
    subject: int,
    weights,
    int8_layers,
    seed: int,
    train_frac: float,
    max_test: int | None,
    epochs: int,
    batch_size: int,
    lr: float,
    train_seed: int,
) -> dict:
    train_q, train_labels, test_q, test_labels = load_subject_split(
        subject, seed, train_frac, max_test
    )
    x_train = featurize(train_q)
    y_train = (train_labels - 1).astype(np.int64)
    x_test = featurize(test_q)
    y_test = (test_labels - 1).astype(np.int64)

    w1, b1, w2, b2, w3, b3 = [w.copy() for w in weights]
    rng = np.random.default_rng(train_seed + subject)

    for ep in range(epochs):
        loss = train_epoch(x_train, y_train, w1, b1, w2, b2, w3, b3, lr, batch_size, rng)
        if ep == 0 or (ep + 1) == epochs:
            print(f"    subject {subject} epoch {ep + 1}/{epochs} loss={loss:.4f}", flush=True)

    _, _, _, _, logits = forward(x_test, w1, b1, w2, b2, w3, b3)
    pred_f = logits.argmax(axis=1)
    acc_f = float(np.mean(pred_f == y_test))

    pred_i = predict_int8(x_test, int8_layers)
    acc_i = float(np.mean(pred_i == y_test))

    return {
        "subject": subject,
        "accuracy_float": acc_f,
        "accuracy_int8": acc_i,
        "accuracy": acc_f,
        "n_train": int(train_q.shape[0]),
        "n_test": int(test_q.shape[0]),
        "n_correct": int((pred_f == y_test).sum()),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tiny int8 MLP EMG baseline")
    p.add_argument("--config", type=Path, default=DEFAULT_BASELINE_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    bcfg = load_json(args.config)
    ecfg = load_json(args.emg_config)
    mlp = bcfg["mlp_int8"]

    if args.quick:
        q = bcfg["quick"]
        subjects = q["subjects"]
        max_test = q["max_test_windows_per_subject"]
        epochs = q["mlp_epochs"]
    else:
        subjects = bcfg["subjects"]
        max_test = None
        epochs = mlp["epochs"]

    seed = int(ecfg["seed"])
    train_frac = float(ecfg["protocol"]["train_fraction"])
    in_dim = mlp["input_dim"]
    h1, h2 = mlp["hidden1"], mlp["hidden2"]
    out_dim = mlp["output_dim"]

    rng = np.random.default_rng(seed + 2000)
    weights = init_mlp(rng, in_dim, h1, h2, out_dim)
    w1, b1, w2, b2, w3, b3 = weights
    n_params = count_params(w1, b1, w2, b2, w3, b3)

    qw1, s1, _ = quantize_affine(w1)
    qw2, s2, _ = quantize_affine(w2)
    qw3, s3, _ = quantize_affine(w3)
    int8_layers = ((qw1, s1, b1), (qw2, s2, b2), (qw3, s3, b3))

    print("=" * 70)
    print(f"MLP int8 baseline  params={n_params}  subjects={subjects}")
    print("=" * 70)

    t0 = time.time()
    rows: List[dict] = []
    for subject in subjects:
        rows.append(
            evaluate_subject(
                subject, weights, int8_layers, seed, train_frac, max_test,
                epochs, mlp["batch_size"], mlp["learning_rate"], seed,
            )
        )

    mean_f = float(np.mean([r["accuracy_float"] for r in rows]))
    mean_i = float(np.mean([r["accuracy_int8"] for r in rows]))

    meta = baseline_meta(
        "mlp_int8",
        ecfg["protocol"],
        {
            "n_params": n_params,
            "architecture": f"{in_dim}-{h1}-{h2}-{out_dim}",
            "epochs": epochs,
            "subjects": subjects,
            "spatial_mean_accuracy_float": mean_f,
            "spatial_mean_accuracy_int8": mean_i,
            "elapsed_s": round(time.time() - t0, 1),
        },
    )

    payload = {"meta": meta, "per_subject": rows}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "mlp_results.json", payload)
    append_summary_csv(
        args.out_dir / "summary.csv",
        [{
            "baseline": "mlp_int8",
            "spatial_mean_accuracy": f"{mean_f:.6f}",
            "n_subjects": len(subjects),
            "n_params": n_params,
            "notes": f"int8 infer {100*mean_i:.2f}%",
        }],
    )

    print(f"\nSpatial mean: float {100*mean_f:.2f}%  int8 {100*mean_i:.2f}%")
    print(f"Wrote {args.out_dir / 'mlp_results.json'}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
