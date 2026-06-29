#!/usr/bin/env python3
"""Host verify: ARM C golden spot-check matches cosim_core (before board run)."""

from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
PYREF = REPO / "python_ref"
SW = REPO / "sw"
LIB = REPO / "build" / "host" / "libhdc_arm_ref.so"
sys.path.insert(0, str(PYREF))

from hdc_ref import HDCConfig, HDCEngine, ItemMemory, pack_u64_words  # noqa: E402

WORDS = 16
N_CLASS = 8


def read_hex_lines(path: Path) -> list[int]:
    out = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("//"):
            out.append(int(s, 16))
    return out


def unpack_grid(l0: int, l1: int, l2: int) -> np.ndarray:
    level_w = 4
    lo = l0 | (l1 << 32)
    hi = l2 & 0xFFFF
    grid = np.zeros((4, 5), dtype=np.int32)
    for c in range(4):
        for f in range(5):
            p = c * 5 + f
            sh = p * level_w
            if sh < 64:
                grid[c, f] = (lo >> sh) & 0xF
            else:
                grid[c, f] = (hi >> (sh - 64)) & 0xF
    return grid


def main() -> int:
    vecdir = PYREF / "vectors" / "cosim_core"
    meta_seed = None
    for line in (vecdir / "meta.txt").read_text().splitlines():
        if line.startswith("seed="):
            meta_seed = int(line.split("=", 1)[1])

    if meta_seed != 42:
        print(f"ERROR: cosim_core seed={meta_seed}, need 42. Run: bash scripts/prep_arm_bench.sh")
        return 1

    if not LIB.is_file():
        subprocess.run(["bash", str(REPO / "scripts" / "build_hdc_arm_host.sh"), "shared"], check=True)

    # Load C library
    lib = ctypes.CDLL(str(LIB))

    class HdcArmMem(ctypes.Structure):
        _fields_ = [
            ("D", ctypes.c_int),
            ("words", ctypes.c_int),
            ("cnt_bits", ctypes.c_int),
            ("cnt_max", ctypes.c_int),
            ("channel", (ctypes.c_uint64 * WORDS) * 4),
            ("feature", (ctypes.c_uint64 * WORDS) * 5),
            ("value", (ctypes.c_uint64 * WORDS) * 16),
        ]

    mem = HdcArmMem()
    lib.hdc_arm_load_mem(ctypes.byref(mem), str(vecdir).encode(), 1024, 6)

    # Protos from core_proto.hex
    proto_lines = read_hex_lines(vecdir / "core_proto.hex")
    protos = np.array(proto_lines, dtype=np.uint64).reshape(N_CLASS, WORDS)

    expects = read_hex_lines(vecdir / "core_expect.hex")
    packed_levels = read_hex_lines(vecdir / "core_levels.hex")

    lib.hdc_arm_encode_grid.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)]
    lib.hdc_arm_classify.argtypes = [
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.hdc_arm_classify.restype = ctypes.c_int

    mask_lines = read_hex_lines(vecdir / "core_mask.hex")
    mask_arr = (ctypes.c_uint64 * WORDS)(*mask_lines)
    errors = 0
    n = min(200, len(expects))

    for i in range(n):
        packed = packed_levels[i]
        l0 = packed & 0xFFFFFFFF
        l1 = (packed >> 32) & 0xFFFFFFFF
        l2 = (packed >> 64) & 0xFFFF
        grid = unpack_grid(l0, l1, l2)
        flat = (ctypes.c_int * 20)(*grid.flatten().tolist())
        q = (ctypes.c_uint64 * WORDS)()
        lib.hdc_arm_encode_grid(ctypes.byref(mem), flat, q)
        p_flat = protos.astype(np.uint64).flatten()
        protos_c = (ctypes.c_uint64 * (N_CLASS * WORDS))(*p_flat.tolist())
        dist = ctypes.c_int()
        pred = lib.hdc_arm_classify(q, protos_c, mask_arr, N_CLASS, WORDS, ctypes.byref(dist))
        expect_cls = (expects[i] >> 16) & 0xFF
        if pred != expect_cls:
            errors += 1

    print(f"Host ARM golden verify: {n - errors}/{n} PASS  (errors={errors})")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
