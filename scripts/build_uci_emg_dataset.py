#!/usr/bin/env python3
"""
Build dataset_36.mat from UCI "EMG Data for Gestures" (36 subjects).

Produces COMPLETE_1..COMPLETE_36 and LABEL_1..LABEL_36 in the same layout as
abbas-rahimi/HDC-EMG/dataset.mat (N x 4 float64 envelope, labels 1..5).

Preprocessing (frozen for Twist 2 @ 36 subjects):
  - Raw MYO 8-channel recordings @ 1 kHz (two trial files per subject)
  - Channels 1,3,5,7 → 4-channel spatial encoder input
  - Bandpass 20–450 Hz (4th-order Butterworth, zero-phase)
  - Full-wave rectification + 100-sample moving-average envelope (~100 ms)
  - Per-channel scale so subject max maps to 20.0 (matches Rahimi mat range)
  - Labels: UCI 0,1 → 1 (rest); 2→2 fist; 3→3 flexion; 4→4 extension; 5→5 radial;
    classes 6,7 dropped (not in 5-class protocol)

Requires:
  data/EMG_data_for_gestures-master/  (download UCI zip into data/)

Usage (from repo root):
  python3 scripts/build_uci_emg_dataset.py
  python3 scripts/build_uci_emg_dataset.py --uci-root data/EMG_data_for_gestures-master \\
      --out python_ref/HDC-EMG/dataset_36.mat --subjects 1-36
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import scipy.io as sio
from scipy.signal import butter, filtfilt

REPO = Path(__file__).resolve().parents[1]
DEFAULT_UCI = REPO / "data" / "EMG_data_for_gestures-master"
DEFAULT_OUT = REPO / "python_ref" / "HDC-EMG" / "dataset_36.mat"

# Evenly spaced MYO channels (1-indexed ch 1,3,5,7).
CHANNEL_IDX = (0, 2, 4, 6)
FS_HZ = 1000.0
BP_LO, BP_HI = 20.0, 450.0
BP_ORDER = 4
ENVELOPE_WIN = 100
SCALE_MAX = 20.0

# UCI class → protocol label (1..5). None = drop sample.
LABEL_MAP = {
    0: 1,  # unmarked / transition → rest
    1: 1,  # hand at rest
    2: 2,  # fist
    3: 3,  # wrist flexion (wave-in)
    4: 4,  # wrist extension (wave-out)
    5: 5,  # radial deviation (fingers-spread proxy)
    6: None,
    7: None,
}


def parse_subjects(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def subject_dir(uci_root: Path, subject: int) -> Path:
    for name in (f"{subject:02d}", str(subject)):
        p = uci_root / name
        if p.is_dir():
            return p
    raise FileNotFoundError(f"subject {subject}: no folder under {uci_root}")


def load_raw_trials(subj_dir: Path) -> np.ndarray:
    files = sorted(subj_dir.glob("*raw_data*.txt"))
    if not files:
        raise FileNotFoundError(f"no raw_data txt in {subj_dir}")
    chunks = [_load_uci_txt(f) for f in files]
    return np.vstack(chunks)


def _load_uci_txt(path: Path) -> np.ndarray:
    """Load one UCI trial; tolerate occasional missing class column."""
    rows: list[list[float]] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        header = f.readline()
        if not header.lower().startswith("time"):
            raise ValueError(f"unexpected header in {path}: {header[:40]!r}")
        prev_class = 0.0
        for line_no, line in enumerate(f, start=2):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            try:
                vals = [float(x) for x in parts]
            except ValueError:
                continue
            if len(vals) == 9:
                vals.append(prev_class)
            elif len(vals) != 10:
                continue
            prev_class = vals[-1]
            rows.append(vals)
    if not rows:
        raise ValueError(f"no data rows parsed from {path}")
    return np.array(rows, dtype=np.float64)


def bandpass(emg: np.ndarray) -> np.ndarray:
    nyq = 0.5 * FS_HZ
    lo, hi = BP_LO / nyq, BP_HI / nyq
    b, a = butter(BP_ORDER, [lo, hi], btype="band")
    return filtfilt(b, a, emg, axis=0)


def moving_average(x: np.ndarray, win: int) -> np.ndarray:
    kernel = np.ones(win, dtype=np.float64) / win
    out = np.empty_like(x)
    for c in range(x.shape[1]):
        out[:, c] = np.convolve(x[:, c], kernel, mode="same")
    return out


def preprocess_subject(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    emg8 = raw[:, 1:9].astype(np.float64)
    uci_labels = raw[:, -1].astype(np.int64)

    mapped: list[int] = []
    keep = np.zeros(len(uci_labels), dtype=bool)
    for i, lab in enumerate(uci_labels):
        m = LABEL_MAP.get(int(lab))
        if m is None:
            continue
        keep[i] = True
        mapped.append(m)
    emg8 = emg8[keep]
    labels = np.array(mapped, dtype=np.int64)

    emg4 = emg8[:, CHANNEL_IDX]
    emg4 = bandpass(emg4)
    env = moving_average(np.abs(emg4), ENVELOPE_WIN)

    peak = float(env.max())
    if peak > 0:
        env = env * (SCALE_MAX / peak)

    return env, labels


def build(uci_root: Path, out_path: Path, subjects: list[int]) -> dict:
    if not uci_root.is_dir():
        raise FileNotFoundError(
            f"UCI root not found: {uci_root}\n"
            "Download: wget -O data/emg_uci.zip "
            "'https://archive.ics.uci.edu/static/public/481/emg+data+for+gestures.zip' "
            "&& unzip -d data data/emg_uci.zip"
        )

    mat: dict = {}
    stats: list[dict] = []
    t0 = time.time()

    for sid in subjects:
        raw = load_raw_trials(subject_dir(uci_root, sid))
        data, labels = preprocess_subject(raw)
        mat[f"COMPLETE_{sid}"] = data
        mat[f"LABEL_{sid}"] = labels.reshape(-1, 1)
        stats.append(
            {
                "subject": sid,
                "n_samples": int(data.shape[0]),
                "labels": [int(x) for x in np.unique(labels)],
                "data_max": float(data.max()),
            }
        )
        print(
            f"  S{sid:2d}: {data.shape[0]:6d} samples  "
            f"labels {stats[-1]['labels']}  max={stats[-1]['data_max']:.3f}",
            flush=True,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sio.savemat(str(out_path), mat, do_compression=True)
    elapsed = time.time() - t0
    return {"out": str(out_path), "n_subjects": len(subjects), "elapsed_s": elapsed, "subjects": stats}


def main() -> int:
    p = argparse.ArgumentParser(description="Build 36-subject UCI EMG dataset.mat")
    p.add_argument("--uci-root", type=Path, default=DEFAULT_UCI)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--subjects", type=str, default="1-36")
    args = p.parse_args()

    subjects = parse_subjects(args.subjects)
    print(f"Building {len(subjects)} subjects → {args.out}", flush=True)
    meta = build(args.uci_root, args.out, subjects)
    print(f"Done in {meta['elapsed_s']:.1f}s  →  {meta['out']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
