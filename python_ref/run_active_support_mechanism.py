#!/usr/bin/env python3
"""
Issue #24 — active support mechanism (value-table ceiling vs real data coverage).

Quantifies why only ~203–210 of D=1024 positions vary on hdc_ref under HDC-2:
  1. Structural ceiling from continuous value item memory (~327 @ seed 42)
  2. Synthetic bundled inputs (uniform envelope vs independent per-slot levels)
  3. Real pooled TRAIN+TEST queries (203–210; cross-ref seed_sensitivity)

Usage (from repo root):
  python3 python_ref/run_active_support_mechanism.py --quick
  python3 python_ref/run_active_support_mechanism.py

Outputs:
  results/protocol_v2/active_support_mechanism/summary.json
  results/protocol_v2/active_support_mechanism/README.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from export_emg_board_vectors import level21_to_grid  # noqa: E402
from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    active_bit_support,
)
from run_active_bit_ablation import diagnose_item_memory, hdc_cfg_for_d, load_json  # noqa: E402

DEFAULT_CFG = HERE / "config" / "active_support_mechanism.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "active_support_mechanism"


def synthetic_bundled_support(
    item_mem_seed: int,
    D: int,
    cnt_w: int,
    n_windows: int,
    gen_grid: Callable,
    *,
    rng_seed: int = 0,
) -> int:
    """Pooled active support over n_windows synthetically encoded bundled queries."""
    cfg = hdc_cfg_for_d(D, item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    rng = np.random.default_rng(rng_seed)
    hvs = np.zeros((n_windows, D), dtype=np.uint8)
    for i in range(n_windows):
        if i > 0 and i % max(1, n_windows // 10) == 0:
            print(f"      synthetic encode: {i}/{n_windows}", flush=True)
        grid = gen_grid(rng, cfg)
        hvs[i] = engine.encode_emg_window(grid, mem, cnt_bits=cnt_w)
    return int(active_bit_support(hvs))


def uniform_envelope_grid(rng: np.random.Generator, cfg: HDCConfig) -> np.ndarray:
    """Random continuous envelope per channel → level21 grid (saturates value table)."""
    q4 = rng.uniform(0.0, 20.0, size=cfg.n_channels)
    return level21_to_grid(q4, cfg)


def independent_slot_grid(rng: np.random.Generator, cfg: HDCConfig) -> np.ndarray:
    """Independent discrete level per (channel, feature) slot."""
    return rng.integers(0, cfg.n_levels, size=(cfg.n_channels, cfg.n_features), dtype=np.int32)


def load_seed_sensitivity(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"seed sensitivity results not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_real_data(seed_payload: dict) -> dict:
    summary = seed_payload["meta"]["summary"]
    per = seed_payload.get("per_subject", [])
    supports = [float(row["spatial_mean_active_bit_support"]) for row in summary]
    per_subject_all = [int(row["active_bit_support"]) for row in per] if per else []
    return {
        "source": str(seed_payload["meta"].get("emg_config", "seed_sensitivity")),
        "item_mem_seeds": [int(row["item_mem_seed"]) for row in summary],
        "spatial_mean_active_bit_support_by_seed": {
            str(int(row["item_mem_seed"])): float(row["spatial_mean_active_bit_support"])
            for row in summary
        },
        "spatial_mean_range": [min(supports), max(supports)],
        "spatial_mean_over_seeds": float(np.mean(supports)),
        "per_subject_active_bit_support_min": min(per_subject_all) if per_subject_all else None,
        "per_subject_active_bit_support_max": max(per_subject_all) if per_subject_all else None,
        "note": "Pooled TRAIN+TEST encoded windows per subject; spatial mean over S1–S5.",
    }


def analyze_seed(
    item_mem_seed: int,
    D: int,
    cnt_w: int,
    n_windows: int,
    *,
    run_synthetic: bool,
) -> dict:
    cfg = hdc_cfg_for_d(D, item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)
    diagnosis = diagnose_item_memory(mem, engine, cfg)

    value_table = int(active_bit_support(mem.value))
    print(
        f"  seed={item_mem_seed}: value_table={value_table} "
        f"per_slot_mean={diagnosis['per_slot_value_path_active_mean']:.0f}",
        flush=True,
    )

    out = {
        "item_mem_seed": item_mem_seed,
        "D": D,
        "value_table_active_bits": value_table,
        "value_minmax_hamming": diagnosis["value_minmax_hamming"],
        "value_flip_budget_D_over_levels": diagnosis["value_flip_budget_D_over_levels"],
        "per_slot_value_path_active_mean": diagnosis["per_slot_value_path_active_mean"],
        "per_slot_value_path_active_max": diagnosis["per_slot_value_path_active_max"],
        "single_record_universe_active_bits": diagnosis["single_record_active_support"],
        "synthetic_n_windows": n_windows if run_synthetic else 0,
        "synthetic_uniform_envelope_bundled": None,
        "synthetic_independent_per_slot_bundled": None,
    }
    if not run_synthetic:
        return out

    uniform_support = synthetic_bundled_support(
        item_mem_seed, D, cnt_w, n_windows, uniform_envelope_grid
    )
    print(f"    uniform envelope bundled (n={n_windows}): {uniform_support}", flush=True)

    independent_support = synthetic_bundled_support(
        item_mem_seed, D, cnt_w, n_windows, independent_slot_grid, rng_seed=1
    )
    print(f"    independent per-slot bundled (n={n_windows}): {independent_support}", flush=True)

    out["synthetic_uniform_envelope_bundled"] = uniform_support
    out["synthetic_independent_per_slot_bundled"] = independent_support
    return out


def paper_table_rows(primary: dict, real: dict) -> List[dict]:
    """Paper-facing table (Discussion guide §5.2)."""
    return [
        {
            "label": "Value-table varying set (structural ceiling)",
            "positions": primary["value_table_active_bits"],
            "of_D": primary["D"],
            "source": f"ItemMemory.value, seed {primary['item_mem_seed']}",
        },
        {
            "label": "Bundled queries, uniform random envelope",
            "positions": primary["synthetic_uniform_envelope_bundled"],
            "of_D": primary["D"],
            "source": f"Synthetic level21 grid, n={primary['synthetic_n_windows']} windows",
        },
        {
            "label": "Bundled queries, independent per-slot levels",
            "positions": primary["synthetic_independent_per_slot_bundled"],
            "of_D": primary["D"],
            "source": f"Synthetic i.i.d. levels, n={primary['synthetic_n_windows']} windows",
        },
        {
            "label": "Bundled queries, real pooled TRAIN+TEST (EMG)",
            "positions_range": real["spatial_mean_range"],
            "positions_mean_over_seeds": real["spatial_mean_over_seeds"],
            "of_D": primary["D"],
            "source": "seed_sensitivity (5 subjects, seeds 1/7/21/42)",
        },
    ]


def write_readme(path: Path, meta: dict, table: List[dict], primary: dict, real: dict) -> None:
    lo, hi = real["spatial_mean_range"]
    lines = [
        "# Issue 24 — active support mechanism (327 vs ~209)",
        "",
        f"Generated: {meta['generated_at']}",
        f"Protocol: **{meta['protocol']}** · Engine: **{meta['engine']}** · D={meta['D']}",
        f"Primary item-memory seed: **{meta['primary_item_mem_seed']}**",
        "",
        "## Paper table (Discussion §5.2)",
        "",
        "| Quantity | Positions (of 1024) |",
        "|----------|---------------------|",
        f"| Value-table varying set — structural ceiling | **{primary['value_table_active_bits']}** |",
        f"| Per (c,f) slot, all 16 levels exercised | **{primary['per_slot_value_path_active_max']:.0f}** |",
        f"| Bundled queries, uniform random envelope (n={primary['synthetic_n_windows']}) | **{primary['synthetic_uniform_envelope_bundled']}** |",
        f"| Bundled queries, independent per-slot levels (n={primary['synthetic_n_windows']}) | **{primary['synthetic_independent_per_slot_bundled']}** |",
        f"| Bundled queries, real pooled data (5 subjects) | **{lo:.0f}–{hi:.0f}** (mean {real['spatial_mean_over_seeds']:.1f}) |",
        "",
        "Discussion guide targets **326 / 316** for bundled saturation (seed 42 / seed 1); "
        "measured independent bundled **319** and seed-1 per-slot path **316** agree within "
        "Monte Carlo count. Uniform envelope uses level21 (4 DOF/window) and sits below the table.",
        "",
        "## Mechanism (one paragraph)",
        "",
        "The encoder's **structural ceiling** is the value item-memory table: only "
        f"**{primary['value_table_active_bits']}** of {primary['D']} bit positions can ever flip under any "
        "input, because channel/feature tables enter as XOR constants and the continuous "
        f"value table walks a Hamming path of length ~D/n_levels ({primary['value_flip_budget_D_over_levels']} "
        "for 16 levels). Synthetic bundled windows that freely sample levels approach that "
        f"ceiling ({primary['synthetic_uniform_envelope_bundled']}–"
        f"{primary['synthetic_independent_per_slot_bundled']} with "
        f"n={primary['synthetic_n_windows']} windows); **real EMG envelopes only exercise "
        f"{lo:.0f}–{hi:.0f} positions** (~{100.0 * real['spatial_mean_over_seeds'] / primary['D']:.0f}% of D), "
        "which is data coverage, not bundling. Hence keep=512 is lossless (512 > ~209 active) "
        "and uniform random @ keep=128 wastes most draws on frozen bits.",
        "",
        "## Per seed (value-table ceiling)",
        "",
        "| Seed | Value table | Per-slot path mean | Uniform synth | Independent synth |",
        "|------|-------------|--------------------|--------------|--------------------|",
    ]
    for row in meta["per_seed"]:
        lines.append(
            f"| {row['item_mem_seed']} | {row['value_table_active_bits']} | "
            f"{row['per_slot_value_path_active_mean']:.0f} | "
            f"{row['synthetic_uniform_envelope_bundled'] if row['synthetic_uniform_envelope_bundled'] is not None else '—'} | "
            f"{row['synthetic_independent_per_slot_bundled'] if row['synthetic_independent_per_slot_bundled'] is not None else '—'} |"
        )
    lines.extend(
        [
            "",
            "## Real EMG (from seed sensitivity)",
            "",
            "| Seed | Spatial mean active support |",
            "|------|----------------------------|",
        ]
    )
    for seed, val in sorted(
        real["spatial_mean_active_bit_support_by_seed"].items(), key=lambda x: int(x[0])
    ):
        lines.append(f"| {seed} | {val:.1f} |")
    lines.extend(
        [
            "",
            "Source: [`seed_sensitivity_results.json`](../../seed_sensitivity/seed_sensitivity_results.json)",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_active_support_mechanism.py --quick",
            "python3 python_ref/run_active_support_mechanism.py",
            "```",
            "",
            "Related: [`active_bits/`](../active_bits/) (issue #5), "
            "[`PAPER_DISCUSSION_GUIDE.md`](../../docs/PAPER_DISCUSSION_GUIDE.md) §5.2",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue 24 active support mechanism")
    p.add_argument("--config", type=Path, default=DEFAULT_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg_doc = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    D = int(cfg_doc["D"])
    cnt_w = int(cfg_doc["cnt_w"])
    primary_seed = int(cfg_doc["primary_item_mem_seed"])
    seeds = list(cfg_doc["item_mem_seeds"])

    if args.quick:
        q = cfg_doc["quick"]
        n_windows = int(q.get("n_synthetic_windows", 1500))
        seeds = list(q.get("item_mem_seeds", [primary_seed]))
    else:
        n_windows = int(cfg_doc["n_synthetic_windows"])

    seed_path = REPO / cfg_doc["seed_sensitivity_results"]
    real = summarize_real_data(load_seed_sensitivity(seed_path))

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Issue 24 — active support mechanism")
    print(f"  D={D}  cnt_w={cnt_w}  synthetic_windows={n_windows}")
    print(f"  item_mem_seeds={seeds}  primary={primary_seed}")
    print("=" * 70)

    t0 = time.time()
    per_seed: List[dict] = []
    for s in seeds:
        run_syn = int(s) == primary_seed
        per_seed.append(analyze_seed(int(s), D, cnt_w, n_windows, run_synthetic=run_syn))
    primary = next(r for r in per_seed if r["item_mem_seed"] == primary_seed)
    table = paper_table_rows(primary, real)

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issue": 24,
        "engine": cfg_doc.get("engine", "hdc_ref"),
        "protocol": emg_cfg.get("protocol", {}).get("id", "HDC-2"),
        "D": D,
        "cnt_w": cnt_w,
        "primary_item_mem_seed": primary_seed,
        "n_synthetic_windows": n_windows,
        "elapsed_s": round(time.time() - t0, 1),
        "paper_table": table,
        "real_emg": real,
        "per_seed": per_seed,
        "conclusions": {
            "structural_ceiling_seed_42": primary["value_table_active_bits"],
            "real_data_spatial_mean_range": real["spatial_mean_range"],
            "gap_ceiling_to_real_mean": round(
                primary["value_table_active_bits"] - real["spatial_mean_over_seeds"], 1
            ),
            "data_coverage_fraction_mean": round(
                real["spatial_mean_over_seeds"] / D, 4
            ),
            "mechanism": (
                "Ceiling set by value item-memory table (~327 @ seed 42); "
                "real EMG uses ~64% of reachable positions (~209 mean); "
                "bundling is not the primary limiter."
            ),
        },
    }

    out_json = args.out_dir / "summary.json"
    out_json.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_readme(args.out_dir / "README.md", meta, table, primary, real)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    print(f"  Value-table ceiling (seed {primary_seed}): {primary['value_table_active_bits']}")
    print(
        f"  Synthetic uniform / independent: "
        f"{primary['synthetic_uniform_envelope_bundled']} / "
        f"{primary['synthetic_independent_per_slot_bundled']}"
    )
    print(
        f"  Real EMG spatial mean range: "
        f"{real['spatial_mean_range'][0]:.0f}–{real['spatial_mean_range'][1]:.0f}"
    )
    print(f"  Wrote {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
