#!/usr/bin/env python3
"""
Plot the committed accuracy / Pareto results as paper-ready figures.

Reads only files already in results/ (nothing recomputed) and writes PNG + PDF
to results/figures/. Mirrors the interactive canvas but produces static figures
for the DATE write-up.

Sources:
  python_ref/results/emg_baseline.json    spatial vs spatiotemporal (MAP + BSC)
  results/baselines/arm_hdc_results.json   per-subject spatial accuracy (HDC)
  results/baselines/mlp_results.json       per-subject spatial accuracy (MLP)
  results/hook_a/sweep_summary.csv         D x CNT_W x keep grid

Usage (from repo root):
  python3 python_ref/plot_results.py
  python3 python_ref/plot_results.py --show        # also open windows
  python3 python_ref/plot_results.py --out results/figures
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe; overridden by --show
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def _load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def load_per_subject() -> dict:
    hdc = _load_json("results/baselines/arm_hdc_results.json")
    mlp = _load_json("results/baselines/mlp_results.json")
    subs = [f"S{r['subject']}" for r in hdc["per_subject"]]
    return {
        "subjects": subs,
        "hdc": [100.0 * r["accuracy"] for r in hdc["per_subject"]],
        "mlp": [100.0 * r["accuracy"] for r in mlp["per_subject"]],
        "hdc_mean": 100.0 * hdc["meta"]["spatial_mean_accuracy"],
        "mlp_mean": 100.0 * mlp["meta"]["spatial_mean_accuracy_int8"],
    }


def load_spatial_temporal() -> dict:
    b = _load_json("python_ref/results/emg_baseline.json")
    pb, pa = b["project_baseline"], b["parity_anchor"]
    return {
        "map": [100.0 * pa["spatial"]["mean"], 100.0 * pa["spatiotemporal"]["mean"]],
        "bsc": [100.0 * pb["spatial"]["mean"], 100.0 * pb["spatiotemporal"]["mean"]],
        "paper": [100.0 * pa["paper"]["spatial"], 100.0 * pa["paper"]["spatiotemporal"]],
    }


def load_hook_a() -> list[dict]:
    rows = []
    with (REPO / "results/hook_a/sweep_summary.csv").open() as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "D": int(r["D"]),
                    "cnt_w": int(r["cnt_w"]),
                    "keep": float(r["keep_ratio"]),
                    "prune": float(r["prune_pct"]),
                    "acc": 100.0 * float(r["spatial_mean_accuracy"]),
                    "energy": float(r["energy_proxy_d_keep"]),
                    "luts": int(r["slice_luts_ooc"]),
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def fig_per_subject(d: dict, out: Path) -> None:
    subs = d["subjects"] + ["Mean"]
    hdc = d["hdc"] + [d["hdc_mean"]]
    mlp = d["mlp"] + [d["mlp_mean"]]
    x = np.arange(len(subs))
    w = 0.38

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.bar(x - w / 2, hdc, w, label="HDC (RTL / ARM)", color="#4c78a8")
    ax.bar(x + w / 2, mlp, w, label="Tiny int8 MLP", color="#59a14f")
    for i, (h, m) in enumerate(zip(hdc, mlp)):
        ax.text(i - w / 2, h + 0.6, f"{h:.1f}", ha="center", va="bottom", fontsize=7)
        ax.text(i + w / 2, m + 0.6, f"{m:.1f}", ha="center", va="bottom", fontsize=7)
    ax.axvline(len(subs) - 1.5, color="0.7", ls="--", lw=0.8)
    ax.set_xticks(x, subs)
    ax.set_ylabel("Spatial accuracy (%)")
    ax.set_ylim(55, 100)
    ax.set_title("Per-subject spatial accuracy — the mean hides HDC's spread")
    ax.legend(loc="lower left")
    _save(fig, out, "per_subject_accuracy")


def fig_spatial_temporal(d: dict, out: Path) -> None:
    cats = ["Spatial", "Spatiotemporal"]
    x = np.arange(len(cats))
    w = 0.38

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.bar(x - w / 2, d["map"], w, label="MAP bipolar D=10k (ours)", color="#59a14f")
    ax.bar(x + w / 2, d["bsc"], w, label="BSC binary D=1024 (RTL-matched)", color="#4c78a8")
    ax.plot(x, d["paper"], "o--", color="0.4", lw=1, ms=4, label="Rahimi paper (MAP)")
    for i in range(len(cats)):
        ax.text(i - w / 2, d["map"][i] + 0.4, f"{d['map'][i]:.1f}", ha="center", fontsize=7)
        ax.text(i + w / 2, d["bsc"][i] + 0.4, f"{d['bsc'][i]:.1f}", ha="center", fontsize=7)
    ax.set_xticks(x, cats)
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(85, 100)
    ax.set_title("Temporal context helps only the high-capacity MAP model")
    ax.legend(loc="lower right", fontsize=8)
    _save(fig, out, "spatial_vs_spatiotemporal")


def fig_hook_a_acc_vs_d(rows: list[dict], out: Path) -> None:
    keep1 = [r for r in rows if r["keep"] == 1.0]
    Ds = sorted({r["D"] for r in keep1})
    cnts = sorted({r["cnt_w"] for r in keep1})

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for c in cnts:
        ys = [next(r["acc"] for r in keep1 if r["D"] == D and r["cnt_w"] == c) for D in Ds]
        style = "o-" if c != 3 else "o--"
        ax.plot([str(D) for D in Ds], ys, style, lw=1.6, ms=5, label=f"CNT_W={c}")
    ax.set_xlabel("Hypervector dimension D")
    ax.set_ylabel("Spatial mean accuracy (%)")
    ax.set_title("Hook A — accuracy vs D and bundle-counter width")
    ax.annotate(
        "CNT_W=3 precision floor\n(bundler saturates → 59.5%)",
        xy=("1024", 59.5), xytext=("512", 64),
        fontsize=8, color="#b4413c",
        arrowprops=dict(arrowstyle="->", color="#b4413c", lw=0.8),
    )
    ax.legend(loc="center right", fontsize=8)
    _save(fig, out, "hookA_accuracy_vs_D")


def fig_hook_a_pareto(rows: list[dict], out: Path) -> None:
    # CNT_W=6, keep=1.0 (unpruned) area/accuracy ladder.
    pts = sorted(
        (r for r in rows if r["cnt_w"] == 6 and r["keep"] == 1.0), key=lambda r: r["luts"]
    )
    luts = [r["luts"] / 1000 for r in pts]
    acc = [r["acc"] for r in pts]
    Ds = [r["D"] for r in pts]
    budget = 53200  # xc7z020 total slice LUTs

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(luts, acc, "o-", color="#4c78a8", lw=1.6, ms=6)
    for L, a, D in zip(luts, acc, Ds):
        over = L * 1000 > budget
        ax.annotate(
            f"D={D}" + ("  (over device)" if over else ""),
            xy=(L, a), xytext=(6, -10 if not over else 6), textcoords="offset points",
            fontsize=8, color="#b4413c" if over else "0.2",
        )
    ax.axvline(budget / 1000, color="#b4413c", ls="--", lw=1)
    ax.text(budget / 1000 - 1, 71.5, "xc7z020 LUT budget", rotation=90,
            va="bottom", ha="right", fontsize=8, color="#b4413c")
    ax.set_xlabel("Slice LUTs, OOC (thousands)")
    ax.set_ylabel("Spatial mean accuracy (%)")
    ax.set_title("Hook A — accuracy vs area Pareto (CNT_W=6, unpruned)")
    _save(fig, out, "hookA_pareto_area")


def fig_hook_a_pruning(rows: list[dict], out: Path) -> None:
    pts = sorted(
        (r for r in rows if r["cnt_w"] == 6 and r["D"] == 1024), key=lambda r: r["prune"]
    )
    prune = [r["prune"] for r in pts]
    acc = [r["acc"] for r in pts]
    energy = [100.0 * r["keep"] for r in pts]  # % of unpruned energy proxy

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(prune, acc, "o-", color="#59a14f", lw=1.8, ms=6, label="Accuracy (%)")
    ax.plot(prune, energy, "s--", color="#4c78a8", lw=1.6, ms=5,
            label="Energy proxy (% of full)")
    ax.set_xlabel("Bits pruned (%) — informed Fisher mask")
    ax.set_ylabel("Percent")
    ax.set_ylim(0, 100)
    ax.set_title("Hook A — pruning is free: accuracy flat, energy proxy 8×↓ (D=1024)")
    ax.legend(loc="center left", fontsize=8)
    _save(fig, out, "hookA_pruning")


# --------------------------------------------------------------------------- #
def _save(fig, out: Path, name: str) -> None:
    fig.tight_layout()
    for ext in ("png", "pdf"):
        p = out / f"{name}.{ext}"
        fig.savefig(p, dpi=200 if ext == "png" else None, bbox_inches="tight")
    print(f"  wrote {name}.png / .pdf")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/figures", help="output dir (rel to repo root)")
    ap.add_argument("--show", action="store_true", help="also open interactive windows")
    args = ap.parse_args()

    if args.show:
        matplotlib.use("TkAgg", force=True)

    out = (REPO / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"Writing figures to {out}")

    fig_per_subject(load_per_subject(), out)
    fig_spatial_temporal(load_spatial_temporal(), out)
    hook = load_hook_a()
    fig_hook_a_acc_vs_d(hook, out)
    fig_hook_a_pareto(hook, out)
    fig_hook_a_pruning(hook, out)

    if args.show:
        plt.show()
    print("Done.")


if __name__ == "__main__":
    main()
