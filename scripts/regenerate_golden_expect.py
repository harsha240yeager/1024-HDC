#!/usr/bin/env python3
"""Recompute golden_expect[200] in sw/golden_vectors.h for a Fisher anchor mask."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python_ref"))
sys.path.insert(0, str(REPO))

from hdc_ref import HDCConfig, HDCEngine, ItemMemory, bits_from_u64_words  # noqa: E402
from scripts.patch_emg_anchor import (  # noqa: E402
    ANCHOR_KEEP,
    build_pooled_fisher_mask,
    load_protos_from_header,
    replace_golden_mask_block,
)
from scripts.export_emg_board_vectors import fmt_mask64  # noqa: E402
from scripts.regenerate_emg_protos import (  # noqa: E402
    DEFAULT_CONFIG,
    N_CLASS,
    unpack_levels_u32,
)

GOLDEN = REPO / "sw" / "golden_vectors.h"


def parse_golden_arrays(text: str) -> tuple[list[int], list[int], list[int], int]:
    def u32_array(name: str) -> list[int]:
        m = re.search(rf"static const u32 {name}\[GOLDEN_N_CASES\] = \{{(.*?)\}};", text, re.S)
        if not m:
            raise ValueError(f"{name} not found")
        return [int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]+)U", m.group(1))]

    m = re.search(r"#define GOLDEN_N_CASES\s+(\d+)U", text)
    n = int(m.group(1)) if m else 200
    return u32_array("golden_levels0"), u32_array("golden_levels1"), u32_array("golden_levels2"), n


def load_golden_protos(text: str, cfg: HDCConfig) -> list:
    m = re.search(r"golden_proto64\[.*?\] = \{(.*?)\};", text, re.S)
    hex_vals = re.findall(r"0x([0-9a-fA-F]+)ULL", m.group(1))
    protos = []
    for k in range(N_CLASS):
        words = [int(hex_vals[k * cfg.words + w], 16) for w in range(cfg.words)]
        protos.append(bits_from_u64_words(words, cfg.D))
    return protos


def replace_expect_block(text: str, expect: list[int]) -> str:
    body = ",\n    ".join(f"0x{v:08x}U" for v in expect)
    block = f"static const u32 golden_expect[GOLDEN_N_CASES] = {{\n    {body}\n}};"
    return re.sub(
        r"static const u32 golden_expect\[GOLDEN_N_CASES\] = \{.*?\};",
        block,
        text,
        count=1,
        flags=re.S,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", choices=sorted(ANCHOR_KEEP), required=True)
    ap.add_argument("--header", type=Path, default=GOLDEN)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = ap.parse_args()

    import json

    cfg_json = json.loads(args.config.read_text(encoding="utf-8"))
    keep = ANCHOR_KEEP[args.anchor]
    cfg = HDCConfig(D=1024, seed=42)
    seed = int(cfg_json["seed"])
    train_frac = float(cfg_json["protocol"]["train_fraction"])
    subjects = cfg_json["dataset"]["subjects"]

    text = args.header.read_text(encoding="utf-8")
    l0, l1, l2, n = parse_golden_arrays(text)
    protos = load_golden_protos(text, cfg)
    mask = build_pooled_fisher_mask(subjects, cfg, seed, train_frac, keep)
    mask_block = fmt_mask64("golden_mask64", mask, cfg).replace("EMG_WORDS64", "GOLDEN_WORDS64")

    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    expect: list[int] = []
    for i in range(n):
        grid = unpack_levels_u32(l0[i], l1[i], l2[i], cfg)
        query = engine.encode_emg_window(grid, mem)
        res = engine.classify(query, protos, mask=mask)
        expect.append((int(res.class_id) << 16) | (int(res.distance) & 0xFFFF))

    text = replace_golden_mask_block(text, mask_block)
    text = replace_expect_block(text, expect)
    args.header.write_text(text, encoding="utf-8")
    print(f"Regenerated golden mask + expect for anchor {args.anchor} (keep={keep}, n={n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
