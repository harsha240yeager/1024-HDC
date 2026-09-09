#!/usr/bin/env python3
"""Pre-gather EMG prototypes for the H1 narrow bitstream (issue #31).

The narrow PL path expects K_BITS-wide prototypes (anchor C: K=128). Software must
gather full-width emg_proto64[] using the same SEL table as rtl/hdc_sel_pkg.sv before
loading prototypes on the board. Mask load is omitted — gather is baked in hardware.

Usage:
  python3 scripts/patch_emg_narrow_protos.py
  python3 scripts/patch_emg_narrow_protos.py --keep 0.125 --header sw/emg_board_vectors_hdc2.h
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "python_ref"))

from hdc_ref import HDCConfig, bits_to_hex_lines, gather_narrow_bits  # noqa: E402
from scripts.gen_sel_table import DEFAULT_NPZ, load_mask  # noqa: E402
from scripts.patch_emg_anchor import load_protos_from_header  # noqa: E402
from scripts.regenerate_emg_protos import parse_defines, parse_subjects  # noqa: E402

DEFAULT_HDR = REPO / "sw" / "emg_board_vectors_hdc2.h"
DEFAULT_SLIM = REPO / "sw" / "emg_board_vectors.h"
BITS_PER_WORD = 64


def fmt_narrow_proto64(protos_n: np.ndarray, k_words: int) -> str:
    """protos_n shape (n_subjects, n_class, k_bits)."""
    lines: list[str] = []
    n_subjects, n_class, _ = protos_n.shape
    for s in range(n_subjects):
        for k in range(n_class):
            row = protos_n[s, k]
            for hex_line in bits_to_hex_lines(row, k_words, BITS_PER_WORD):
                lines.append(f"0x{int(hex_line, 16):016x}ULL")
    body = ",\n    ".join(lines)
    return (
        "static const u64 emg_proto_narrow64[EMG_N_SUBJECTS * EMG_N_CLASS * EMG_K_WORDS] = {\n"
        f"    {body}\n"
        "};"
    )


def inject_narrow_defines(text: str, k_bits: int, k_words: int) -> str:
    block = (
        f"#define EMG_NARROW                     1U\n"
        f"#define EMG_K_BITS                     {k_bits}U\n"
        f"#define EMG_K_WORDS                    {k_words}U"
    )
    if re.search(r"^#define EMG_NARROW\b", text, flags=re.M):
        text = re.sub(r"^#define EMG_NARROW\b.*$", f"#define EMG_NARROW                     1U", text, flags=re.M)
        text = re.sub(r"^#define EMG_K_BITS\b.*$", f"#define EMG_K_BITS                     {k_bits}U", text, flags=re.M)
        text = re.sub(r"^#define EMG_K_WORDS\b.*$", f"#define EMG_K_WORDS                    {k_words}U", text, flags=re.M)
        return text
    anchor = "#define EMG_WORDS64"
    if anchor not in text:
        raise ValueError("EMG_WORDS64 define not found")
    return text.replace(anchor, block + "\n" + anchor, 1)


def replace_narrow_proto_block(text: str, proto_block: str) -> str:
    pat = r"static const u64 emg_proto_narrow64\[.*?\] = \{.*?\};"
    if re.search(pat, text, flags=re.S):
        return re.sub(pat, proto_block, text, count=1, flags=re.S)
    anchor = "static const u64 emg_mask64"
    if anchor not in text:
        raise ValueError("emg_mask64 block not found — cannot insert emg_proto_narrow64")
    return text.replace(anchor, proto_block + "\n\n" + anchor, 1)


def patch_header(path: Path, proto_block: str, k_bits: int, k_words: int) -> None:
    text = path.read_text(encoding="utf-8")
    text = inject_narrow_defines(text, k_bits, k_words)
    text = replace_narrow_proto_block(text, proto_block)
    path.write_text(text, encoding="utf-8")
    print(f"Patched narrow protos in {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-gather EMG protos for narrow bitstream")
    ap.add_argument("--keep", type=float, default=0.125, help="frozen mask keep ratio (default anchor C)")
    ap.add_argument("--npz", type=Path, default=DEFAULT_NPZ)
    ap.add_argument("--header", type=Path, default=DEFAULT_HDR)
    ap.add_argument("--slim-header", type=Path, default=DEFAULT_SLIM)
    args = ap.parse_args()

    if not args.slim_header.is_file():
        raise SystemExit(f"missing {args.slim_header}")
    header_for_protos = args.header if args.header.is_file() else args.slim_header

    defs = parse_defines(args.slim_header)
    subjects = parse_subjects(defs, args.slim_header)
    cfg = HDCConfig(D=1024, seed=int(defs.get("EMG_ITEM_MEM_SEED", 42)))

    mask, key = load_mask(args.npz, args.keep)
    sel = np.flatnonzero(mask).astype(np.int32)
    k_bits = int(sel.size)
    k_words = (k_bits + BITS_PER_WORD - 1) // BITS_PER_WORD

    protos_all = load_protos_from_header(header_for_protos, cfg, len(subjects))
    protos_n = np.zeros((len(subjects), 8, k_bits), dtype=np.uint8)
    for s in range(len(subjects)):
        for k in range(8):
            protos_n[s, k] = gather_narrow_bits(protos_all[s, k], sel)

    proto_block = fmt_narrow_proto64(protos_n, k_words)
    print(f"Gathered {len(subjects)} subjects x 8 classes -> K_BITS={k_bits} ({key})")

    for path in (args.slim_header, args.header if args.header.is_file() else None):
        if path is None:
            continue
        patch_header(path, proto_block, k_bits, k_words)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
