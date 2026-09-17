#!/usr/bin/env python3
"""Aggregate 3-run INA219 energy folders into per-anchor tables and energy_summary.txt."""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = REPO / "results" / "phase3" / "energy_runs"
NARROW_RUNS = REPO / "results" / "protocol_v2" / "narrow_rtl" / "energy_runs"


def parse_summary(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, float] = {}

    def grab(label: str, key: str) -> None:
        m = re.search(rf"^{re.escape(label)}\s*:\s*([0-9.+-eE]+)", text, re.M)
        if m:
            out[key] = float(m.group(1))

    grab("Static power (mW)", "static_mw")
    grab("Total energy per window (uJ)", "total_uj")
    grab("Dynamic energy per window (uJ)", "dynamic_uj")
    grab("Batch duration (ms)", "batch_ms")
    return out


def aggregate_anchor(anchor: str, runs_root: Path) -> list[dict]:
    base = runs_root / f"anchor_{anchor}"
    rows: list[dict] = []
    for run_dir in sorted(base.glob("run*")):
        summary = run_dir / "energy_batch.txt"
        if not summary.is_file():
            continue
        m = parse_summary(summary)
        m["run"] = run_dir.name
        rows.append(m)
    return rows


def fmt_pm(values: list[float], scale: float = 1.0) -> str:
    if not values:
        return "n/a"
    mean = statistics.mean(values) / scale
    if len(values) > 1:
        std = statistics.stdev(values) / scale
        return f"{mean:.2f} ± {std:.2f}"
    return f"{mean:.2f}"


def write_anchor_readme(anchor: str, rows: list[dict], runs_root: Path) -> None:
    base = runs_root / f"anchor_{anchor}"
    base.mkdir(parents=True, exist_ok=True)
    static = [r["static_mw"] for r in rows if "static_mw" in r]
    total = [r["total_uj"] for r in rows if "total_uj" in r]
    dynamic = [r["dynamic_uj"] for r in rows if "dynamic_uj" in r]
    lines = [
        f"# Anchor {anchor} — INA219 (3 runs, pooled Fisher mask in golden + emg)",
        "",
        "| Run | Static (mW) | Total (µJ/w) | Dynamic (µJ/w) |",
        "|-----|-------------|--------------|----------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['run']} | {r.get('static_mw', 0):.1f} | "
            f"{r.get('total_uj', 0):.2f} | {r.get('dynamic_uj', 0):.3f} |"
        )
    lines += [
        "",
        f"**Mean ± std:** static **{fmt_pm(static)} mW**; "
        f"total **{fmt_pm(total)} µJ/w**; dynamic **{fmt_pm(dynamic)} µJ/w**",
        "",
    ]
    (base / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {base / 'README.md'}")


def write_global_summary(
    anchors: dict[str, list[dict]],
    path: Path,
    *,
    title: str,
    mask_note: str,
    footer: list[str] | None = None,
) -> None:
    lines = [
        title,
        "=" * 62,
        "Method: ZedBoard J21 + INA219 on Pi; cal_ref_mv=2.0; batch integration",
        mask_note,
        "",
    ]
    for anchor in ("A", "B", "C", "ARM"):
        rows = anchors.get(anchor, [])
        if not rows:
            continue
        static = [r["static_mw"] for r in rows if "static_mw" in r]
        total = [r["total_uj"] for r in rows if "total_uj" in r]
        dynamic = [r["dynamic_uj"] for r in rows if "dynamic_uj" in r]
        keep_map = {
            "A": "1.0",
            "B": "0.5",
            "C": "0.125",
            "ARM": "1.0 (ARM PS path)",
        }
        keep = keep_map.get(anchor, "0.125 (narrow K=128)")
        lines += [
            f"Anchor {anchor} (keep={keep}, n={len(rows)})",
            f"  Static (mW):     {fmt_pm(static)}",
            f"  Total (µJ/w):    {fmt_pm(total)}",
            f"  Dynamic (µJ/w):  {fmt_pm(dynamic)}",
            "",
        ]
    if footer:
        lines.extend(footer)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", help="A, B, C, ARM, or C for narrow runs")
    ap.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    ap.add_argument("--write-summary", action="store_true")
    ap.add_argument(
        "--write-narrow-summary",
        action="store_true",
        help="Write results/protocol_v2/narrow_rtl/energy_summary.txt",
    )
    args = ap.parse_args()
    runs = args.runs_root

    if args.anchor:
        rows = aggregate_anchor(args.anchor, runs)
        write_anchor_readme(args.anchor, rows, runs)
        return 0

    if args.write_summary:
        anchors = {a: aggregate_anchor(a, runs) for a in ("A", "B", "C", "ARM")}
        for a, rows in anchors.items():
            if rows:
                write_anchor_readme(a, rows, runs)
        write_global_summary(
            anchors,
            REPO / "results" / "phase3" / "energy_summary.txt",
            title="Phase 3 — Energy measurement summary (self-consistent, pooled Fisher masks)",
            mask_note="Mask: same pooled Fisher mask in sw/golden_vectors.h AND sw/emg_board_vectors.h",
            footer=[
                "Note: Anchor A re-measured with Fisher keep=1.0 (all-ones), "
                "replacing legacy cosim golden_mask runs.",
                "ARM row uses PS software batch (~164 ms / 200 windows); "
                "PL rows use DMA batch (~0.93 ms / 200).",
            ],
        )
        return 0

    if args.write_narrow_summary:
        rows = aggregate_anchor("C", runs)
        if rows:
            write_anchor_readme("C", rows, runs)
        write_global_summary(
            {"C": rows},
            REPO / "results" / "protocol_v2" / "narrow_rtl" / "energy_summary.txt",
            title="Narrow PL — Energy @ anchor C (K=128, keep=0.125, n=3)",
            mask_note="Bitstream: design_1_wrapper.narrow.bit; bench: Final_HDC_dma_bench_narrow.elf",
            footer=[
                "Compare to baseline PL anchor C in results/phase3/energy_summary.txt.",
            ],
        )
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
