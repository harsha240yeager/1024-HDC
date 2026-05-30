#!/usr/bin/env python3
"""
Stage B - the project's own BSC (binary) baseline on Rahimi's EMG data.

Same envelope encoding as Stage A, but re-cast in the Binary Spatter Code model
that the 1024-bit RTL actually implements:
    - hypervectors are binary {0,1}
    - bind        = XOR              (xor_permute_top.sv)
    - permute     = cyclic shift     (permute_stage.sv)
    - bundle      = thresholded majority, tie -> 0   (bundle_unit.sv)
    - similarity  = Hamming distance / popcount       (popcount_am.sv)

This produces the headline project baseline at D = 1024 and a D-sweep that feeds
Hook A. The gap between this and the Stage-A MAP/D=10000 numbers is itself a
reported, honest result.

Spatial record for one sample:  R = majority_c( iM[c] XOR CiM_c(v_c) )
N-gram:                         G = majority_t( rho^t( R[t] ) )
Class prototype (AM):           P_k = majority over all training G of class k
Classify:                       argmin Hamming(G, P_k)

Usage:
    python stage_b_bsc.py [--dims 256 512 1024 2048 4096 10000]
                          [--subjects 1 2 3 4 5] [--mode spatial|both] [--seed 1]
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
MAXL = 21
PERCISION = 1
N_CLASSES = 5
BEST_N = {1: 4, 2: 4, 3: 3, 4: 5, 5: 4}
DS_SPATIOTEMPORAL = {1: 250, 2: 250, 3: 250, 4: 250, 5: 50}


# --------------------------------------------------------------------------- #
# Binary item memory
# --------------------------------------------------------------------------- #
def gen_random_bits(D, rng):
    hv = np.zeros(D, dtype=np.uint8)
    idx = rng.permutation(D)
    hv[idx[: D // 2]] = 1
    return hv


def init_item_memories(D, rng):
    """iM: (4, D) channel HVs; CiM: (22, D) continuous binary level memory."""
    iM = np.stack([gen_random_bits(D, rng) for _ in range(4)]).astype(np.uint8)
    current = gen_random_bits(D, rng)
    rand_idx = rng.permutation(D)
    SP = D // 2 // MAXL
    CiM = np.empty((MAXL + 1, D), dtype=np.uint8)
    for i in range(MAXL + 1):
        CiM[i] = current
        start = i * SP
        end = (i + 1) * SP + 1
        current = current.copy()
        current[rand_idx[start:end]] ^= 1          # binary flip (NOT)
    return CiM, iM


def majority(stack_sum, n):
    """Thresholded majority over n binary vectors; tie (n even) -> 0."""
    return (stack_sum * 2 > n).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Encoding
# --------------------------------------------------------------------------- #
def build_bind_tables(CiM, iM):
    """T[c, level] = iM[c] XOR CiM[level]  -> (4, 22, D)."""
    return (CiM[None, :, :] ^ iM[:, None, :]).astype(np.uint8)


def records_for(T, q):
    """Spatial records for all samples: majority over 4 bound channels. -> (n, D)."""
    s = T[0, q[:, 0]].astype(np.int16)
    for c in range(1, 4):
        s += T[c, q[:, c]]
    return majority(s, 4)


def ngram_block(records, idx, N, D):
    """N-gram from records[idx:idx+N]: majority over rho^t(R[t])."""
    s = np.zeros(D, dtype=np.int16)
    for t in range(N):
        s += np.roll(records[idx + t], t)
    return majority(s, N)


def quantize(data):
    return np.clip((data * PERCISION).astype(np.int64), 0, MAXL)


def downsample(data, labels, rate):
    return (data, labels) if rate <= 1 else (data[::rate], labels[::rate])


def gen_train_data(data, labels, frac, rng):
    parts_d, parts_l = [], []
    for cls in range(1, 8):
        idx = np.where(labels == cls)[0]
        if idx.size == 0:
            continue
        idx = idx[: int(np.floor(idx.size * frac))]
        idx = idx[rng.permutation(idx.size)]
        parts_d.append(data[idx])
        parts_l.append(labels[idx])
    return np.concatenate(parts_d, 0), np.concatenate(parts_l, 0)


# --------------------------------------------------------------------------- #
# Train / predict via majority prototypes + Hamming
# --------------------------------------------------------------------------- #
def train_prototypes(grams, labels, D):
    """P_k = majority over class-k n-grams. Returns (6, D) uint8 (row 0 unused)."""
    P = np.zeros((N_CLASSES + 1, D), dtype=np.uint8)
    for k in range(1, N_CLASSES + 1):
        sel = grams[labels == k]
        if len(sel):
            P[k] = majority(sel.sum(0), len(sel))
    return P


def predict(grams, P):
    """argmax matching bits == argmin Hamming. Bipolar dot trick."""
    g = grams.astype(np.int16) * 2 - 1            # (n, D) in {-1,+1}
    p = P.astype(np.int16) * 2 - 1                # (6, D)
    scores = (g @ p.T).astype(np.int32)           # (n, 6)
    scores[:, 0] = -(10 ** 9)
    return scores.argmax(1)


# --------------------------------------------------------------------------- #
# Spatial / spatiotemporal drivers
# --------------------------------------------------------------------------- #
def run_spatial(T, q_train, y_train, q_test, y_test, D):
    rec_tr = records_for(T, q_train)
    rec_te = records_for(T, q_test)
    P = train_prototypes(rec_tr, y_train, D)
    pred = predict(rec_te, P)
    return float(np.mean(pred == y_test))


def run_spatiotemporal(T, q_train, y_train, q_test, y_test, N, D):
    rec_tr = records_for(T, q_train)
    rec_te = records_for(T, q_test)
    # training n-grams over stable windows (stride 1, skip transitions)
    g_tr, l_tr = [], []
    i, n = 0, len(y_train)
    while i < n - N + 1:
        if y_train[i] == y_train[i + N - 1]:
            g_tr.append(ngram_block(rec_tr, i, N, D))
            l_tr.append(int(y_train[i + N - 1]))
            i += 1
        else:
            i += N - 1
    P = train_prototypes(np.array(g_tr, dtype=np.uint8), np.array(l_tr), D)
    # test with stride N (matches hdcpredict windowing)
    g_te, l_te = [], []
    for i in range(0, len(y_test) - N + 1, N):
        g_te.append(ngram_block(rec_te, i, N, D))
        vals, cnts = np.unique(y_test[i:i + N], return_counts=True)
        l_te.append(int(vals[cnts.argmax()]))
    pred = predict(np.array(g_te, dtype=np.uint8), P)
    return float(np.mean(pred == np.array(l_te)))


def run(dims, subjects, mode, seed):
    mat = sio.loadmat(str(DATASET))
    results = {"seed": seed, "spatial": {}, "spatiotemporal": {}}

    for D in dims:
        sp, st = {}, {}
        for s in subjects:
            data = mat[f"COMPLETE_{s}"].astype(np.float64)
            labels = mat[f"LABEL_{s}"].ravel().astype(np.int64)
            rng = np.random.default_rng(seed)
            CiM, iM = init_item_memories(D, rng)
            T = build_bind_tables(CiM, iM)

            ts_d, ts_l = downsample(data, labels, 1)
            tr_d, tr_l = gen_train_data(ts_d, ts_l, LEARNING_FRAC, np.random.default_rng(seed + 100))
            sp[s] = run_spatial(T, quantize(tr_d), tr_l, quantize(ts_d), ts_l, D)

            if mode == "both":
                N, ds = BEST_N[s], DS_SPATIOTEMPORAL[s]
                td, tl = downsample(data, labels, ds)
                rd, rl = gen_train_data(td, tl, LEARNING_FRAC, np.random.default_rng(seed + 100))
                st[s] = run_spatiotemporal(T, quantize(rd), rl, quantize(td), tl, N, D)

        sp["mean"] = float(np.mean([sp[s] for s in subjects]))
        results["spatial"][D] = sp
        line = f"D={D:>5}  spatial mean={sp['mean']*100:6.2f}%  " + \
               " ".join(f"S{s}={sp[s]*100:5.1f}" for s in subjects)
        if st:
            st["mean"] = float(np.mean([st[s] for s in subjects]))
            results["spatiotemporal"][D] = st
            line += f"   |  st mean={st['mean']*100:6.2f}%"
        print(line)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", type=int, nargs="+", default=[256, 512, 1024, 2048, 4096, 10000])
    ap.add_argument("--subjects", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--mode", choices=["spatial", "both"], default="both")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "stage_b_results.json")
    args = ap.parse_args()

    print(f"Stage B (BSC binary)  dims={args.dims}  subjects={args.subjects}  mode={args.mode}\n")
    t0 = time.time()
    res = run(args.dims, args.subjects, args.mode, args.seed)
    args.out.write_text(json.dumps(res, indent=2))
    print(f"\n  elapsed {time.time()-t0:.1f}s   results -> {args.out}")
    if 1024 in res["spatial"]:
        m = res["spatial"][1024]["mean"] * 100
        print(f"\n  >>> PROJECT BASELINE  D=1024 spatial = {m:.2f}%  (RTL-matched BSC model)")


if __name__ == "__main__":
    main()
