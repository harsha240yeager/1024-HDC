#!/usr/bin/env python3
"""Issue #32 — baseline vs narrow Pareto-style figure (committed CSV only)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "results" / "figures" / "narrow_vs_baseline_pareto.csv"
CAPTION = REPO / "results" / "figures" / "narrow_vs_baseline_pareto_caption.txt"


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser(description="Plot narrow vs baseline Pareto (#32)")
    ap.add_argument("--csv", type=Path, default=CSV_PATH)
    ap.add_argument("--out", type=Path, default=REPO / "results" / "figures")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--paper", action="store_true")
    args = ap.parse_args()

    rows = [r for r in load_rows(args.csv) if r["scope"] == "integrated_placed"]
    if len(rows) < 2:
        raise SystemExit("need baseline+narrow integrated rows in CSV")

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8 if args.paper else 10,
            "savefig.dpi": args.dpi,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
        }
    )

    fig, axes = plt.subplots(1, 3, figsize=(6.8 if args.paper else 9.0, 2.4))
    colors = {"baseline": "#2166ac", "narrow": "#d95f02"}
    labels = {"baseline": "Baseline PL", "narrow": "Narrow PL (K=128)"}

    for r in rows:
        v = r["variant"]
        c = colors[v]
        lab = labels[v]

        lut = int(r["lut"])
        us = float(r["batch_us_per_window"])
        e = float(r["energy_uj_per_window"]) if r["energy_uj_per_window"] else None
        acc = float(r["accuracy_pct_anchor_c"])

        axes[0].bar(v, lut, color=c, width=0.55, label=lab)
        axes[1].bar(v, us, color=c, width=0.55)
        if e is not None:
            axes[2].bar(v, e, color=c, width=0.55)

        axes[0].text(v, lut * 1.02, f"{lut:,}", ha="center", va="bottom", fontsize=7)
        axes[1].text(v, us * 1.05, f"{us:.1f}", ha="center", va="bottom", fontsize=7)
        if e is not None:
            axes[2].text(v, e * 1.05, f"{e:.2f}", ha="center", va="bottom", fontsize=7)

    axes[0].set_ylabel("Slice LUTs (placed)")
    axes[1].set_ylabel("Batch latency (µs/window)")
    axes[2].set_ylabel("Energy (µJ/window)")
    for ax in axes:
        ax.set_xticks(range(len(rows)))
        ax.set_xticklabels([labels[r["variant"]] for r in rows], rotation=15, ha="right")
        ax.grid(axis="y", alpha=0.25, linewidth=0.5)

    if not args.paper:
        fig.suptitle(
            f"Anchor C @ keep=0.125 — accuracy {rows[0]['accuracy_pct_anchor_c']}% "
            f"(493k windows, iso-accuracy band)",
            fontsize=9,
        )

    fig.tight_layout()
    stem = "narrow_vs_baseline_pareto"
    for ext in ("png", "pdf"):
        out = args.out / f"{stem}.{ext}"
        fig.savefig(out)
        print(f"Wrote {out}")

    cap = (
        "Baseline vs narrow gated PL at Fisher anchor C (keep=0.125, 493,512 EMG windows). "
        "Narrow reduces integrated LUT and DMA batch latency at matched board accuracy; "
        "system energy at J21 remains flat (mask does not change measured µJ/w until "
        "narrow INA219 campaign completes). OOC BD-wrapper LUT rows are in "
        "narrow_vs_baseline_pareto.csv."
    )
    CAPTION.write_text(cap + "\n")
    print(f"Wrote {CAPTION}")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
