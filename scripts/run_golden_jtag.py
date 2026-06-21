#!/usr/bin/env python3
"""
Host-side golden test over JTAG (xsdb mwr/mrd @ 0x43C00000).

Use when UART is unavailable or the app already finished before serial capture.
Requires: PL programmed, PS7 initialized, hw_server running.

Usage (from repo root):
  python3 scripts/run_golden_jtag.py [vecdir]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

HDC_BASE = 0x43C00000
REG_CTRL = HDC_BASE + 0x000
REG_STATUS = HDC_BASE + 0x004
REG_PROTO_IDX = HDC_BASE + 0x008
REG_RESULT = HDC_BASE + 0x00C
REG_LEVELS0 = HDC_BASE + 0x010
REG_LEVELS1 = HDC_BASE + 0x014
REG_LEVELS2 = HDC_BASE + 0x018
REG_STAGING = HDC_BASE + 0x100

CTRL_START = 0x1
CTRL_LOAD_PROTO = 0x2
CTRL_LOAD_MASK = 0x4
CTRL_CLR_DONE = 0x8
STATUS_DONE = 0x2

IDX_W = 3
DIST_W = 11
VEC_WORDS = 32
WORDS64 = 16
N_CLASS = 8

XSDB = "/cad/Xilinx/Vitis/2024.2/bin/loader"
HW_URL = "tcp:127.0.0.1:3121"


def read_hex_lines(path: Path) -> list[int]:
    vals: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("//"):
            vals.append(int(s, 16))
    return vals


def proto32(proto_lines: list[int], class_idx: int, word_idx: int) -> int:
    flat = class_idx * WORDS64 + (word_idx >> 1)
    w64 = proto_lines[flat]
    return (w64 >> 32) if (word_idx & 1) else (w64 & 0xFFFFFFFF)


def mask32(mask_lines: list[int], word_idx: int) -> int:
    w64 = mask_lines[word_idx >> 1]
    return (w64 >> 32) if (word_idx & 1) else (w64 & 0xFFFFFFFF)


class XsdbSession:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [XSDB, "-exec", "rdi_xsdb"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert self.proc.stdin and self.proc.stdout
        self._run(f"connect -url {HW_URL}", wait_prompt=True)

    def _run(self, cmd: str, wait_prompt: bool = False) -> str:
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        if not wait_prompt:
            return ""
        lines: list[str] = []
        deadline = time.time() + 30.0
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            lines.append(line.rstrip())
            if line.strip().endswith("xsdb%") or line.strip().endswith("xsdb% "):
                break
        return "\n".join(lines)

    def mwr(self, addr: int, val: int) -> None:
        out = self._run(f"mwr -force {addr:#x} {val:#x}", wait_prompt=True)
        if "ERROR" in out or "error" in out.lower():
            raise RuntimeError(f"mwr failed: {out}")

    def mrd(self, addr: int) -> int:
        out = self._run(f"mrd -force {addr:#x}", wait_prompt=True)
        m = re.search(r":\s+([0-9a-fA-Fx]+)", out)
        if not m:
            m = re.search(r"0x([0-9a-fA-F]+)", out)
        if not m:
            raise RuntimeError(f"mrd parse failed: {out!r}")
        token = m.group(1)
        return int(token, 16 if token.lower().startswith("0x") else 16 if "x" in token.lower() else 10)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.write("exit\n")
            self.proc.stdin.flush()
        self.proc.wait(timeout=10)


def fill_staging(xs: XsdbSession, words: list[int]) -> None:
    for i, w in enumerate(words):
        xs.mwr(REG_STAGING + i * 4, w & 0xFFFFFFFF)


def load_proto(xs: XsdbSession, class_idx: int, proto_lines: list[int]) -> None:
    staging = [proto32(proto_lines, class_idx, w) for w in range(VEC_WORDS)]
    fill_staging(xs, staging)
    xs.mwr(REG_PROTO_IDX, class_idx)
    xs.mwr(REG_CTRL, CTRL_LOAD_PROTO)


def load_mask(xs: XsdbSession, mask_lines: list[int]) -> None:
    staging = [mask32(mask_lines, w) for w in range(VEC_WORDS)]
    fill_staging(xs, staging)
    xs.mwr(REG_CTRL, CTRL_LOAD_MASK)


def classify(xs: XsdbSession, lvl0: int, lvl1: int, lvl2: int) -> tuple[int, int]:
    xs.mwr(REG_LEVELS0, lvl0)
    xs.mwr(REG_LEVELS1, lvl1)
    xs.mwr(REG_LEVELS2, lvl2)
    xs.mwr(REG_CTRL, CTRL_START)
    for _ in range(2_000_000):
        status = xs.mrd(REG_STATUS)
        if status & STATUS_DONE:
            break
    else:
        raise TimeoutError("inference timed out")

    result = xs.mrd(REG_RESULT)
    xs.mwr(REG_CTRL, CTRL_CLR_DONE)
    idx = (result >> 16) & ((1 << IDX_W) - 1)
    dist = result & ((1 << DIST_W) - 1)
    return idx, dist


def main() -> int:
    ap = argparse.ArgumentParser(description="JTAG golden test for HDC core")
    ap.add_argument(
        "vecdir",
        nargs="?",
        type=Path,
        default=Path("python_ref/vectors/cosim_core"),
    )
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    vecdir = (root / args.vecdir).resolve()

    proto = read_hex_lines(vecdir / "core_proto.hex")
    mask = read_hex_lines(vecdir / "core_mask.hex")
    levels = read_hex_lines(vecdir / "core_levels.hex")
    expect = read_hex_lines(vecdir / "core_expect.hex")
    n_cases = len(expect)

    print(f"HDC JTAG golden test: {n_cases} cases from {vecdir}")
    xs = XsdbSession()
    errors = 0
    try:
        for k in range(N_CLASS):
            load_proto(xs, k, proto)
        load_mask(xs, mask)

        for c in range(n_cases):
            exp = expect[c]
            exp_idx = (exp >> 16) & ((1 << IDX_W) - 1)
            exp_dist = exp & ((1 << DIST_W) - 1)
            lvl0 = levels[c * 3 + 0]
            lvl1 = levels[c * 3 + 1]
            lvl2 = levels[c * 3 + 2]
            try:
                got_idx, got_dist = classify(xs, lvl0, lvl1, lvl2)
            except TimeoutError:
                errors += 1
                print(f"FAIL case {c}: inference timed out")
                continue
            if got_idx != exp_idx or got_dist != exp_dist:
                errors += 1
                print(
                    f"FAIL case {c}: expected idx={exp_idx} dist={exp_dist}, "
                    f"got idx={got_idx} dist={got_dist}"
                )
    finally:
        xs.close()

    print("=" * 50)
    if errors == 0:
        print(f"PASS: {n_cases}/{n_cases} golden cases")
        return 0
    print(f"FAIL: {errors} errors / {n_cases} checked")
    return 1


if __name__ == "__main__":
    sys.exit(main())
