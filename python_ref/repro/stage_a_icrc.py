#!/usr/bin/env python3
"""
Stage A - literal parity reproduction of Rahimi et al. (ICRC 2016).

Faithful NumPy port of the authors' MATLAB reference (HDC-EMG/ICRC.m +
generatePaperFigures.m). MAP model: bipolar {-1,+1} hypervectors, bind =
element-wise multiply, bundle = integer addition, permute = cyclic shift by 1,
similarity = cosine. D = 10000, 21-level continuous item memory, conditional-add
training (cos < 0.9), 25% training fraction.

Goal: reproduce the published numbers
    - spatial only (N=1)          ~ 90.8% mean over 5 subjects
    - spatiotemporal (best N)     ~ 97.8% mean over 5 subjects

The MATLAB RNG cannot be byte-matched in NumPy, so the random basis differs;
accuracy reproduces to within run-to-run noise (the paper's robustness claim).

Usage:
    python stage_a_icrc.py [--D 10000] [--subjects 1 2 3 4 5]
                           [--mode spatial|spatiotemporal|both] [--seed 1]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import scipy.io as sio

REPO = Path(__file__).resolve().parent.parent / "HDC-EMG"
DATASET = REPO / "dataset.mat"

LEARNING_FRAC = 0.25
CUTTING_ANGLE = 0.9
MAXL = 21                      # 22 level vectors: 0..21
PERCISION = 1
N_CLASSES = 5
# Best n-gram per subject from Table I of the paper.
BEST_N = {1: 4, 2: 4, 3: 3, 4: 5, 5: 4}
# Downsampling used for the spatiotemporal experiment (generatePaperFigures.m).
DS_SPATIOTEMPORAL = {1: 250, 2: 250, 3: 250, 4: 250, 5: 50}


# --------------------------------------------------------------------------- #
# Item-memory construction (ports genRandomHV + initItemMemories)
# --------------------------------------------------------------------------- #
def gen_random_hv(D: int, rng: np.random.Generator) -> np.ndarray:
    """Bipolar HV with exactly D/2 of each sign (genRandomHV)."""
    hv = np.empty(D, dtype=np.int8)
    idx = rng.permutation(D)
    hv[idx[: D // 2]] = 1
    hv[idx[D // 2:]] = -1
    return hv


def init_item_memories(D: int, rng: np.random.Generator):
    """Return (CiM, iM): continuous level memory (22 x D) and 4 channel HVs."""
    iM = np.stack([gen_random_hv(D, rng) for _ in range(4)]).astype(np.int8)

    init_hv = gen_random_hv(D, rng)
    current = init_hv.copy()
    rand_idx = rng.permutation(D)
    SP = D // 2 // MAXL
    CiM = np.empty((MAXL + 1, D), dtype=np.int8)
    for i in range(MAXL + 1):
        CiM[i] = current
        start = i * SP
        end = (i + 1) * SP + 1          # MATLAB inclusive range -> +1
        current = current.copy()
        current[rand_idx[start:end]] *= -1
    return CiM, iM


# --------------------------------------------------------------------------- #
# Data helpers (port genTrainData + downSampling)
# --------------------------------------------------------------------------- #
def downsample(data, labels, rate):
    if rate <= 1:
        return data, labels
    return data[::rate], labels[::rate]


def gen_train_data(data, labels, frac, rng: np.random.Generator):
    """First `frac` of each class (in original order) then shuffled within class."""
    parts_d, parts_l = [], []
    for cls in range(1, 8):
        idx = np.where(labels == cls)[0]
        if idx.size == 0:
            continue
        idx = idx[: int(np.floor(idx.size * frac))]
        perm = rng.permutation(idx.size)
        idx = idx[perm]
        parts_d.append(data[idx])
        parts_l.append(labels[idx])
    return np.concatenate(parts_d, 0), np.concatenate(parts_l, 0)


def quantize(data):
    return np.clip((data * PERCISION).astype(np.int64), 0, MAXL)


# --------------------------------------------------------------------------- #
# Encoding (port computeNgram / computeSumHV)
# --------------------------------------------------------------------------- #
def build_record_tables(CiM, iM):
    """L[c, level] = CiM[level] * iM[c]  -> shape (4, 22, D)."""
    return (CiM[None, :, :].astype(np.int32) * iM[:, None, :].astype(np.int32))


def record_hv(L, q_row):
    """Spatial record for one sample: sum_c L[c, q_c]  (MAP bind+bundle)."""
    return L[0, q_row[0]] + L[1, q_row[1]] + L[2, q_row[2]] + L[3, q_row[3]]


def compute_ngram(L, q_block, N, D):
    """N-gram via permutation: Ngram = ((... (R1)>>1 * R2)>>1 ...) * RN."""
    ngram = record_hv(L, q_block[0]).astype(np.int64)
    for t in range(1, N):
        rec = record_hv(L, q_block[t]).astype(np.int64)
        ngram = np.roll(ngram, 1) * rec
    return ngram


def compute_sum_hv(L, q_window, N, D):
    out = np.zeros(D, dtype=np.int64)
    for i in range(len(q_window) - N + 1):
        out += compute_ngram(L, q_window[i:i + N], N, D)
    return out


def cos(u, v):
    nu = np.linalg.norm(u)
    nv = np.linalg.norm(v)
    if nu == 0 or nv == 0:
        return np.nan
    return float(np.dot(u, v) / (nu * nv))


# --------------------------------------------------------------------------- #
# Spatial (N=1) train + predict, vectorised exactly
# --------------------------------------------------------------------------- #
def train_spatial(L, q_train, y_train, D):
    AM = np.zeros((N_CLASSES + 1, D), dtype=np.int64)
    numpat = np.zeros(N_CLASSES + 1, dtype=int)
    for i in range(len(y_train)):
        lbl = int(y_train[i])
        ng = record_hv(L, q_train[i]).astype(np.int64)
        if cos(ng, AM[lbl]) < CUTTING_ANGLE or np.isnan(cos(ng, AM[lbl])):
            AM[lbl] += ng
            numpat[lbl] += 1
    return AM, numpat


def predict_spatial(L, q_test, y_test, AM, D):
    """Exact cosine NN, decomposed: dot(AM,sig)=sum_c PcL[label,c,q_c]."""
    # PcL[label, c, level] = dot(AM[label], L[c, level])
    PcL = np.einsum("ld,cvd->lcv", AM.astype(np.float64), L.astype(np.float64))
    normAM = np.linalg.norm(AM.astype(np.float64), axis=1)  # (6,)
    scores = np.zeros((len(q_test), N_CLASSES + 1))
    for c in range(4):
        scores += PcL[:, c, q_test[:, c]].T            # (samples, labels)
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = scores / normAM[None, :]
    scores[:, 0] = -np.inf                              # label 0 unused
    scores[np.isnan(scores)] = -np.inf
    pred = scores.argmax(axis=1)
    return float(np.mean(pred == y_test))


# --------------------------------------------------------------------------- #
# Spatiotemporal train + slicing test (ports hdctrain / test_slicing)
# --------------------------------------------------------------------------- #
def train_spatiotemporal(L, q_train, y_train, N, D):
    AM = np.zeros((N_CLASSES + 1, D), dtype=np.int64)
    numpat = np.zeros(N_CLASSES + 1, dtype=int)
    i = 0
    n = len(y_train)
    while i < n - N + 1:
        if y_train[i] == y_train[i + N - 1]:
            ng = compute_ngram(L, q_train[i:i + N], N, D)
            lbl = int(y_train[i + N - 1])
            a = cos(ng, AM[lbl])
            if np.isnan(a) or a < CUTTING_ANGLE:
                AM[lbl] += ng
                numpat[lbl] += 1
            i += 1
        else:
            i += N - 1
    return AM, numpat


def predict_window_max(L, q_block, AM, N, D):
    best_angle, best_label = -1.0, -1
    for i in range(len(q_block) - N + 1):
        sig = compute_sum_hv(L, q_block[i:i + N], N, D)
        for lbl in range(1, N_CLASSES + 1):
            a = cos(AM[lbl], sig)
            if a > best_angle:
                best_angle, best_label = a, lbl
    return best_label


def test_slicing(L, q_test, y_test, AM, N, D):
    correct = numtests = 0
    n = len(y_test)
    start = n - 1
    i = 0
    while i < n - 1:
        if y_test[i] == y_test[i + 1] and start > i:
            start = i
        elif y_test[i] != y_test[i + 1] and start <= i:
            stop = i
            window = max(stop - start, N)
            if start >= 1 and stop + window <= n - 1:
                pred = predict_window_max(L, q_test[start:start + window + 1], AM, N, D)
                numtests += 1
                if pred == y_test[start]:
                    correct += 1
            start = n - 1
        i += 1
    return correct / numtests if numtests else 0.0


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def run(D, subjects, mode, seed):
    mat = sio.loadmat(str(DATASET))
    results = {"D": D, "seed": seed, "spatial": {}, "spatiotemporal": {}}

    for s in subjects:
        data = mat[f"COMPLETE_{s}"].astype(np.float64)
        labels = mat[f"LABEL_{s}"].ravel().astype(np.int64)
        rng = np.random.default_rng(seed)
        CiM, iM = init_item_memories(D, rng)
        L = build_record_tables(CiM, iM)

        if mode in ("spatial", "both"):
            t0 = time.time()
            ts_d, ts_l = downsample(data, labels, 1)
            tr_d, tr_l = gen_train_data(ts_d, ts_l, LEARNING_FRAC, np.random.default_rng(seed + 100))
            AM, _ = train_spatial(L, quantize(tr_d), tr_l, D)
            acc = predict_spatial(L, quantize(ts_d), ts_l, AM, D)
            results["spatial"][s] = acc
            print(f"  S{s} spatial  N=1  acc={acc*100:6.2f}%  ({time.time()-t0:5.1f}s)")

        if mode in ("spatiotemporal", "both"):
            t0 = time.time()
            N = BEST_N[s]
            ds = DS_SPATIOTEMPORAL[s]
            ts_d, ts_l = downsample(data, labels, ds)
            tr_d, tr_l = gen_train_data(ts_d, ts_l, LEARNING_FRAC, np.random.default_rng(seed + 100))
            AM, _ = train_spatiotemporal(L, quantize(tr_d), tr_l, N, D)
            acc = test_slicing(L, quantize(ts_d), ts_l, AM, N, D)
            results["spatiotemporal"][s] = acc
            print(f"  S{s} st  N={N} ds={ds}  acc={acc*100:6.2f}%  ({time.time()-t0:5.1f}s)")

    def mean(d):
        return float(np.mean(list(d.values()))) if d else None

    if results["spatial"]:
        m = mean(results["spatial"])
        results["spatial"]["mean"] = m
        print(f"\n  SPATIAL mean over {len(subjects)} subj = {m*100:.2f}%  (paper 90.8%)")
    if results["spatiotemporal"]:
        m = mean(results["spatiotemporal"])
        results["spatiotemporal"]["mean"] = m
        print(f"  SPATIOTEMPORAL mean = {m*100:.2f}%  (paper 97.8%)")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--D", type=int, default=10000)
    ap.add_argument("--subjects", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--mode", choices=["spatial", "spatiotemporal", "both"], default="both")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "stage_a_results.json")
    args = ap.parse_args()

    print(f"Stage A (ICRC MAP)  D={args.D}  subjects={args.subjects}  mode={args.mode}")
    res = run(args.D, args.subjects, args.mode, args.seed)
    args.out.write_text(json.dumps(res, indent=2))
    print(f"\n  results -> {args.out}")


if __name__ == "__main__":
    main()
