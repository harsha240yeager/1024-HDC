#!/usr/bin/env python3
"""Pack existing sw/emg_board_vectors.h arrays into DDR binary + slim header (no re-export)."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_HDR = REPO / "sw" / "emg_board_vectors.h"
DEFAULT_BIN = REPO / "sw" / "emg_board_vectors.bin"
DEFAULT_SLIM = REPO / "sw" / "emg_board_vectors.h"
DDR_BASE = 0x02000000

DEFINE_RE = re.compile(r"#define\s+(\w+)\s+(\d+)U")
HEX_U32_RE = re.compile(r"0x([0-9a-fA-F]+)U")
DEC_U8_RE = re.compile(r"\b(\d{1,3})\b")


def parse_defines(path: Path) -> dict[str, int]:
    defs: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:80]:
        m = DEFINE_RE.search(line)
        if m:
            defs[m.group(1)] = int(m.group(2))
    return defs


def stream_u32_array(path: Path, marker: str) -> list[int]:
    vals: list[int] = []
    active = False
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not active:
                if marker in line and "static const u32" in line:
                    active = True
                continue
            if line.strip().startswith("};"):
                break
            for m in HEX_U32_RE.finditer(line):
                vals.append(int(m.group(1), 16) & 0xFFFFFFFF)
    if not vals:
        raise ValueError(f"no u32 data found for {marker}")
    return vals


def stream_u8_array(path: Path, marker: str) -> list[int]:
    vals: list[int] = []
    active = False
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not active:
                if marker in line and "static const u8" in line:
                    active = True
                continue
            if line.strip().startswith("};"):
                break
            for m in DEC_U8_RE.finditer(line):
                v = int(m.group(1))
                if v <= 255:
                    vals.append(v)
    if not vals:
        raise ValueError(f"no u8 data found for {marker}")
    return vals


def extract_proto_mask_block(path: Path, start_marker: str) -> str:
    lines: list[str] = []
    active = False
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not active:
                if start_marker in line and "static const u64" in line:
                    active = True
                    lines.append(line.rstrip())
                continue
            lines.append(line.rstrip())
            if line.strip() == "};":
                break
    return "\n".join(lines)


def write_slim_header(
    path: Path,
    defs: dict[str, int],
    offsets: dict[str, int],
    comment_lines: list[str],
    proto_block: str,
    mask_block: str,
    subj_windows_line: str,
    engine_stage_b: bool,
) -> None:
    engine_line = (
        "#define EMG_ENGINE_STAGE_B          1U"
        if engine_stage_b
        else "#define EMG_ENGINE_HDC_REF          1U"
    )

    lines = comment_lines + [
        "/* EMG_USE_DDR_VECTORS: window arrays in sw/emg_board_vectors.bin @ DDR */",
        "#ifndef EMG_BOARD_VECTORS_H",
        "#define EMG_BOARD_VECTORS_H",
        "",
        '#include "xil_types.h"',
        "",
        "#define EMG_USE_DDR_VECTORS             1U",
        f"#define EMG_VECTORS_DDR_BASE            0x{DDR_BASE:08X}U",
        f"#define EMG_OFF_LEVELS0                 {offsets['levels0']}U",
        f"#define EMG_OFF_LEVELS1                 {offsets['levels1']}U",
        f"#define EMG_OFF_LEVELS2                 {offsets['levels2']}U",
        f"#define EMG_OFF_LABELS                  {offsets['labels']}U",
        f"#define EMG_OFF_WINDOW_SUBJECT          {offsets['window_subject']}U",
        f"#define EMG_OFF_EXPECT                  {offsets['expect']}U",
        "",
        f"#define EMG_EXPORT_VERSION              {defs.get('EMG_EXPORT_VERSION', 2)}U",
        engine_line,
        f"#define EMG_BOARD_WINDOWS               {defs['EMG_BOARD_WINDOWS']}U",
        f"#define EMG_N_SUBJECTS                  {defs.get('EMG_N_SUBJECTS', 1)}U",
        f"#define EMG_N_CLASS                     {defs.get('EMG_N_CLASS', 8)}U",
        f"#define EMG_WORDS64                     {defs.get('EMG_WORDS64', 16)}U",
        f"#define EMG_SEED                        {defs.get('EMG_SEED', 1)}U",
        f"#define EMG_ITEM_MEM_SEED               {defs.get('EMG_ITEM_MEM_SEED', 42)}U",
        f"#define EMG_EXPORT_REF_ACCURACY_X1000   {defs['EMG_EXPORT_REF_ACCURACY_X1000']}U",
        "",
    ]
    if subj_windows_line:
        lines.append(subj_windows_line)
        lines.append("")
    lines.append(proto_block)
    lines.append("")
    lines.append(mask_block)
    lines.append("")
    lines.append("#endif")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--header", type=Path, default=DEFAULT_HDR)
    ap.add_argument("--bin", type=Path, default=DEFAULT_BIN)
    ap.add_argument("--out-header", type=Path, default=DEFAULT_SLIM)
    args = ap.parse_args()

    if not args.header.is_file():
        raise SystemExit(f"missing {args.header}")

    print(f"Reading {args.header} ...")
    defs = parse_defines(args.header)
    n = defs.get("EMG_BOARD_WINDOWS")
    if not n:
        raise SystemExit("EMG_BOARD_WINDOWS not found in header")

    comment_lines: list[str] = []
    with args.header.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("/*"):
                comment_lines.append(line.rstrip())
            if line.strip().endswith("*/"):
                comment_lines.append(line.rstrip())
                break

    print("  parsing levels0 ...")
    l0 = stream_u32_array(args.header, "emg_levels0")
    print("  parsing levels1 ...")
    l1 = stream_u32_array(args.header, "emg_levels1")
    print("  parsing levels2 ...")
    l2 = stream_u32_array(args.header, "emg_levels2")
    print("  parsing labels ...")
    labels = stream_u8_array(args.header, "emg_labels")
    print("  parsing window_subject ...")
    subj = stream_u8_array(args.header, "emg_window_subject")
    print("  parsing expect ...")
    expect = stream_u32_array(args.header, "emg_expect")

    for name, arr, want in [
        ("levels0", l0, n),
        ("levels1", l1, n),
        ("levels2", l2, n),
        ("labels", labels, n),
        ("window_subject", subj, n),
        ("expect", expect, n),
    ]:
        if len(arr) != want:
            raise SystemExit(f"{name}: expected {want}, got {len(arr)}")

    off_l0 = 0
    off_l1 = off_l0 + n * 4
    off_l2 = off_l1 + n * 4
    off_labels = off_l2 + n * 4
    off_subj = off_labels + n
    off_subj = (off_subj + 3) & ~3
    off_expect = off_subj + n
    off_expect = (off_expect + 3) & ~3
    total = off_expect + n * 4

    offsets = {
        "levels0": off_l0,
        "levels1": off_l1,
        "levels2": off_l2,
        "labels": off_labels,
        "window_subject": off_subj,
        "expect": off_expect,
    }

    print(f"Writing {args.bin} ({total / 1e6:.1f} MB) ...")
    args.bin.parent.mkdir(parents=True, exist_ok=True)
    with args.bin.open("wb") as f:
        f.write(struct.pack(f"<{n}I", *l0))
        f.write(struct.pack(f"<{n}I", *l1))
        f.write(struct.pack(f"<{n}I", *l2))
        f.write(bytes(labels))
        pad = off_subj - (off_labels + n)
        if pad:
            f.write(b"\x00" * pad)
        f.write(bytes(subj))
        pad = off_expect - (off_subj + n)
        if pad:
            f.write(b"\x00" * pad)
        f.write(struct.pack(f"<{n}I", *expect))

    proto_block = extract_proto_mask_block(args.header, "emg_proto64")
    mask_block = extract_proto_mask_block(args.header, "emg_mask64")

    subj_windows_line = ""
    engine_stage_b = False
    with args.header.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if "emg_subj_windows" in line:
                subj_windows_line = line.rstrip()
            if "EMG_ENGINE_STAGE_B" in line:
                engine_stage_b = True

    write_slim_header(
        args.out_header, defs, offsets, comment_lines,
        proto_block, mask_block, subj_windows_line, engine_stage_b,
    )

    print(f"Wrote slim header {args.out_header}")
    print(f"DDR base 0x{DDR_BASE:08X}, total bin {total} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
