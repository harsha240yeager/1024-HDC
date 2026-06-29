#!/usr/bin/env python3
"""
ARM-only HDC baseline — portable C (hdc_ref / encoder_top semantics).

Same EMG protocol and item memory as the 74.24% RTL board path. Uses a host-built
libhdc_arm_ref.so on VDI for accuracy; cross-compile the same C for Cortex-A9
timing/energy when the board is available.

Usage (repo root):
  python3 python_ref/run_arm_hdc_baseline.py
  python3 python_ref/run_arm_hdc_baseline.py --quick
  python3 python_ref/run_arm_hdc_baseline.py --verify-only
"""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from baseline_common import (  # noqa: E402
    DEFAULT_BASELINE_CFG,
    DEFAULT_EMG_CFG,
    OUT_DIR,
    append_summary_csv,
    baseline_meta,
    cap_train_windows,
    load_json,
    load_subject_split,
    write_json,
)
from export_emg_board_vectors import (  # noqa: E402
    N_CLASS,
    require_dataset,
)
from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    pack_u64_words,
)

LIB_PATH = REPO / "build" / "host" / "libhdc_arm_ref.so"
BUILD_SCRIPT = REPO / "scripts" / "build_hdc_arm_host.sh"
WORDS = 16
N_CH = 4
N_FEAT = 5


def ensure_mem_files(mem_dir: Path, seed: int, D: int) -> None:
    if (mem_dir / "item_mem_channel.mem").is_file():
        return
    mem_dir.mkdir(parents=True, exist_ok=True)
    cfg = HDCConfig(D=D, words=D // 64, bits_per_word=64, seed=seed)
    ItemMemory(cfg).export_mem_files(mem_dir)


def build_library() -> Path:
    subprocess.run(["bash", str(BUILD_SCRIPT), "shared"], check=True, cwd=str(REPO))
    if not LIB_PATH.is_file():
        raise FileNotFoundError(f"library not built: {LIB_PATH}")
    return LIB_PATH


class HdcArmLib:
    def __init__(self, lib_path: Path) -> None:
        self.lib = ctypes.CDLL(str(lib_path))
        self._setup()

    def _setup(self) -> None:
        self.lib.hdc_arm_load_mem.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.lib.hdc_arm_load_mem.restype = ctypes.c_int
        self.lib.hdc_arm_sample_to_grid.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.hdc_arm_sample_to_grid.restype = None
        self.lib.hdc_arm_encode_grid.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint64),
        ]
        self.lib.hdc_arm_encode_grid.restype = None
        self.lib.hdc_arm_classify.argtypes = [
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.hdc_arm_classify.restype = ctypes.c_int
        self.lib.hdc_arm_train_proto.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint64),
        ]
        self.lib.hdc_arm_train_proto.restype = ctypes.c_int

        class HdcArmMem(ctypes.Structure):
            _fields_ = [
                ("D", ctypes.c_int),
                ("words", ctypes.c_int),
                ("cnt_bits", ctypes.c_int),
                ("cnt_max", ctypes.c_int),
                ("channel", (ctypes.c_uint64 * WORDS) * N_CH),
                ("feature", (ctypes.c_uint64 * WORDS) * N_FEAT),
                ("value", (ctypes.c_uint64 * WORDS) * 16),
            ]

        self.HdcArmMem = HdcArmMem
        self.mem = HdcArmMem()

    def load(self, mem_dir: Path, D: int, cnt_bits: int) -> None:
        rc = self.lib.hdc_arm_load_mem(
            ctypes.byref(self.mem),
            str(mem_dir).encode(),
            D,
            cnt_bits,
        )
        if rc != 0:
            raise RuntimeError(f"hdc_arm_load_mem failed from {mem_dir}")

    def encode_sample(self, sample_q4: np.ndarray) -> np.ndarray:
        samp = (ctypes.c_int * N_CH)(* [int(sample_q4[i]) for i in range(N_CH)])
        grid_flat = (ctypes.c_int * (N_CH * N_FEAT))()
        self.lib.hdc_arm_sample_to_grid(samp, grid_flat)
        out = (ctypes.c_uint64 * WORDS)()
        self.lib.hdc_arm_encode_grid(ctypes.byref(self.mem), grid_flat, out)
        return np.array(out, dtype=np.uint64)

    def classify(
        self,
        query_u64: np.ndarray,
        protos_u64: np.ndarray,
        mask_u64: np.ndarray,
    ) -> Tuple[int, int]:
        q = (ctypes.c_uint64 * WORDS)(*query_u64.tolist())
        p_flat = protos_u64.astype(np.uint64).flatten()
        protos = (ctypes.c_uint64 * (N_CLASS * WORDS))(*p_flat.tolist())
        m = (ctypes.c_uint64 * WORDS)(*mask_u64.tolist())
        dist = ctypes.c_int()
        cls = self.lib.hdc_arm_classify(q, protos, m, N_CLASS, WORDS, ctypes.byref(dist))
        return int(cls), int(dist.value)

    def train_class_proto(
        self,
        train_q: np.ndarray,
        class_indices: np.ndarray,
    ) -> np.ndarray:
        flat = train_q.astype(np.int32).flatten()
        samples = (ctypes.c_int * flat.size)(*flat.tolist())
        idx = (ctypes.c_int * class_indices.size)(*class_indices.astype(np.int32).tolist())
        out = (ctypes.c_uint64 * WORDS)()
        rc = self.lib.hdc_arm_train_proto(
            ctypes.byref(self.mem),
            samples,
            int(train_q.shape[0]),
            idx,
            int(class_indices.size),
            out,
        )
        if rc != 0:
            raise RuntimeError("hdc_arm_train_proto failed")
        return np.array(out, dtype=np.uint64)


def bits_to_u64(bits: np.ndarray, words: int) -> np.ndarray:
    return pack_u64_words(bits, words, 64)


def train_prototypes_c(
    arm: HdcArmLib,
    train_q: np.ndarray,
    train_labels: np.ndarray,
) -> np.ndarray:
    protos_u64 = np.zeros((N_CLASS, WORDS), dtype=np.uint64)
    for k in range(1, N_CLASS + 1):
        idx = np.where(train_labels == k)[0]
        if idx.size == 0:
            continue
        protos_u64[k - 1] = arm.train_class_proto(train_q, idx)
    return protos_u64


def verify_encode(arm: HdcArmLib, engine: HDCEngine, mem: ItemMemory, cfg: HDCConfig,
                  samples: np.ndarray, cnt_bits: int, n: int = 32) -> int:
    mism = 0
    for i in range(min(n, samples.shape[0])):
        from export_emg_board_vectors import level21_to_grid  # noqa: WPS433
        py = engine.encode_emg_window(level21_to_grid(samples[i], cfg), mem, cnt_bits=cnt_bits)
        py_u64 = bits_to_u64(py, WORDS)
        c_u64 = arm.encode_sample(samples[i])
        if not np.array_equal(py_u64, c_u64):
            mism += 1
    return mism


def evaluate_subject(
    subject: int,
    arm: HdcArmLib,
    seed: int,
    train_frac: float,
    max_train: int | None,
    max_test: int | None,
) -> dict:
    train_q, train_labels, test_q, test_labels = load_subject_split(
        subject, seed, train_frac, max_test
    )
    train_q, train_labels = cap_train_windows(train_q, train_labels, max_train)
    print(f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}", flush=True)

    t_train = time.time()
    protos_u64 = train_prototypes_c(arm, train_q, train_labels)
    print(f"      train protos {time.time() - t_train:.1f}s", flush=True)

    mask_u64 = np.full(WORDS, np.uint64(0xFFFFFFFFFFFFFFFF), dtype=np.uint64)

    correct = 0
    n = test_q.shape[0]
    step = max(1, n // 10)
    t_test = time.time()
    for i in range(n):
        if i > 0 and i % step == 0:
            print(f"      classify {i}/{n}", flush=True)
        q_u64 = arm.encode_sample(test_q[i])
        pred, _ = arm.classify(q_u64, protos_u64, mask_u64)
        gt = int(test_labels[i]) - 1
        if pred == gt:
            correct += 1
    print(f"      test {n} windows {time.time() - t_test:.1f}s", flush=True)

    acc = correct / n if n else 0.0
    return {
        "subject": subject,
        "accuracy": acc,
        "correct": correct,
        "n_test": n,
        "n_train": int(train_q.shape[0]),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ARM HDC C baseline")
    p.add_argument("--config", type=Path, default=DEFAULT_BASELINE_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--verify-only", action="store_true")
    p.add_argument("--no-build", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    bcfg = load_json(args.config)
    ecfg = load_json(args.emg_config)
    acfg = bcfg["arm_hdc"]

    if args.quick:
        q = bcfg["quick"]
        subjects = q["subjects"]
        max_test = q.get("max_test_windows_per_subject")
        max_train = q.get("max_train_windows_per_subject")
    else:
        subjects = bcfg["subjects"]
        max_test = None
        max_train = None

    D = acfg["D"]
    seed = int(ecfg["seed"])
    train_frac = float(ecfg["protocol"]["train_fraction"])
    item_mem_seed = acfg["item_mem_seed"]
    cnt_bits = acfg["cnt_bits"]
    mem_dir = HERE / acfg["mem_dir"]

    ensure_mem_files(mem_dir, item_mem_seed, D)
    if not args.no_build:
        build_library()
    arm = HdcArmLib(LIB_PATH)
    arm.load(mem_dir, D, cnt_bits)

    cfg = HDCConfig(D=D, words=D // 64, bits_per_word=64, seed=item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)

    # verification on subject 1 train samples
    train_q, _, _, _ = load_subject_split(1, seed, train_frac, 100)
    mism = verify_encode(arm, engine, mem, cfg, train_q, cnt_bits, 32)
    print(f"Encode verify: {32 - mism}/32 match Python hdc_ref")
    if mism > 0:
        print("WARNING: C encode mismatch vs Python — check hdc_arm_ref.c", flush=True)
    if args.verify_only:
        return 0 if mism == 0 else 1

    print("=" * 70)
    print(f"ARM HDC baseline (C)  D={D} CNT_W={cnt_bits}  subjects={subjects}")
    print(f"  max_train={max_train or 'all'}  max_test={max_test or 'all'}")
    print("=" * 70)

    t0 = time.time()
    rows: List[dict] = []
    for subject in subjects:
        rows.append(
            evaluate_subject(
                subject, arm, seed, train_frac, max_train, max_test,
            )
        )

    mean_acc = float(np.mean([r["accuracy"] for r in rows]))
    meta = baseline_meta(
        "arm_hdc_c",
        ecfg["protocol"],
        {
            "D": D,
            "cnt_bits": cnt_bits,
            "item_mem_seed": item_mem_seed,
            "subjects": subjects,
            "max_train_windows_per_subject": max_train,
            "max_test_windows_per_subject": max_test,
            "spatial_mean_accuracy": mean_acc,
            "encode_verify_mismatches": mism,
            "library": str(LIB_PATH),
            "elapsed_s": round(time.time() - t0, 1),
            "board_timing_energy": "pending — cross-compile sw/hdc_arm_ref.c for Zynq bench",
        },
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "arm_hdc_results.json", {"meta": meta, "per_subject": rows})
    append_summary_csv(
        args.out_dir / "summary.csv",
        [{
            "baseline": "arm_hdc_c",
            "spatial_mean_accuracy": f"{mean_acc:.6f}",
            "n_subjects": len(subjects),
            "n_params": "N/A",
            "notes": f"encode verify mism={mism}",
        }],
    )

    print(f"\nSpatial mean accuracy: {100 * mean_acc:.2f}%")
    print(f"Wrote {args.out_dir / 'arm_hdc_results.json'}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
