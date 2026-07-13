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
  results/phase3/energy_summary.txt        measured INA219 anchors A/B/C/ARM
  results/phase3/anchors/anchor_*/board_emg_replay.txt  on-board accuracy
  results/hook_a/fisher_pooled.npz           pooled Fisher scores + masks (export script)
  results/twist1/twist1_results.json         Twist 1 informed vs random @ keep=0.5
  results/twist2/twist2_results.json         Twist 2 cross-subject mask transfer (5-subject pilot)
  results/twist2_36/twist2_results.json    Twist 2 @ 36 UCI subjects (train 1–18 → test 19–36)

Usage (from repo root):
  python3 python_ref/plot_results.py
  python3 python_ref/plot_results.py --show        # also open windows
  python3 python_ref/plot_results.py --out results/figures
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe; overridden by --show
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

# Publication defaults (IEEE/DATE two-column friendly).
PAPER_DPI = 300
PAPER_COLORS = {
    "blue": "#2166ac",
    "green": "#1b7837",
    "orange": "#d95f02",
    "red": "#b2182b",
    "purple": "#7570b3",
    "gray": "#636363",
}


def apply_paper_style(dpi: int = PAPER_DPI, paper: bool = False) -> None:
    """Matplotlib rcParams for print-ready PNG/PDF (editable vector text)."""
    font_size = 8 if paper else 10
    tick_size = 7 if paper else 9
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif", "serif"],
            "font.size": font_size,
            "axes.labelsize": font_size,
            "axes.titlesize": font_size,
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
            "xtick.labelsize": tick_size,
            "ytick.labelsize": tick_size,
            "legend.fontsize": tick_size,
            "figure.titlesize": 11,
            "savefig.dpi": dpi,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "lines.linewidth": 1.5,
            "lines.markersize": 5,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.5,
        }
    )


PAPER_MODE = False


def _paper_tick_labels(names: list[str]) -> list[str]:
    short = {
        "PL DMA\n(batch)": "PL",
        "ARM HDC\n(PS)": "ARM",
        "MLP\nint8": "MLP",
    }
    return [short.get(n, n.replace("\n", " ")) for n in names]


# Native width (in) for IEEE single-column figures; height tuned per layout.
IEEE_COL_W = 3.5


def panel_tag(ax, label: str) -> None:
    """Single subplot letter tag for LaTeX (caption carries the figure title)."""
    ax.text(
        0.03,
        0.97,
        label,
        transform=ax.transAxes,
        fontsize=8,
        fontweight="bold",
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.85),
    )


def set_figure_title(ax, panel: str | None, full: str) -> None:
    """LaTeX caption carries titles and panel letters; paper mode leaves axes bare."""
    if PAPER_MODE:
        ax.set_title("")
        return
    ax.set_title(full)


def _save(fig, out: Path, name: str, dpi: int | None = None) -> None:
    if dpi is None:
        dpi = int(plt.rcParams["savefig.dpi"])
    if PAPER_MODE:
        try:
            fig.tight_layout(pad=0.2, w_pad=0.35, h_pad=0.35)
        except Exception:
            pass
    else:
        fig.tight_layout(rect=(0, 0.03, 1, 0.98))
    for ext in ("png", "pdf"):
        p = out / f"{name}.{ext}"
        fig.savefig(
            p,
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.02 if PAPER_MODE else 0.03,
            facecolor="white",
            edgecolor="none",
        )
    print(f"  wrote {name}.png / .pdf @ {dpi} dpi")


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


def load_measured_silicon() -> list[dict]:
    """INA219 batch energy + on-board EMG accuracy at Hook A silicon anchors."""
    energy_path = REPO / "results/phase3/energy_summary.txt"
    text = energy_path.read_text(encoding="utf-8")
    pts: list[dict] = []
    block = None
    for line in text.splitlines():
        m = re.match(r"Anchor (\w+) \(keep=([^,]+)", line)
        if m:
            block = m.group(1)
            continue
        if block and "Total (µJ/w):" in line:
            mean_s, std_s = line.split(":")[1].strip().split("±")
            uj = float(mean_s.strip())
            uj_std = float(std_s.strip())
            acc = None
            replay = REPO / f"results/phase3/anchors/anchor_{block}/board_emg_replay.txt"
            if replay.is_file():
                rm = re.search(r"accuracy=(\d+\.\d+)%", replay.read_text(encoding="utf-8"))
                if rm:
                    acc = float(rm.group(1))
            if block == "ARM" and acc is None:
                acc = 74.15
            pts.append(
                {
                    "anchor": block,
                    "keep": {"A": 1.0, "B": 0.5, "C": 0.125, "ARM": 1.0}[block],
                    "uj": uj,
                    "uj_std": uj_std,
                    "acc": acc,
                    "path": "ARM" if block == "ARM" else "PL",
                }
            )
            block = None
    return pts


def load_fisher_pooled() -> dict:
    """Pooled Fisher scores + informed masks (16×64 bit layout)."""
    path = REPO / "results/hook_a/fisher_pooled.npz"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path} — run: python3 scripts/export_fisher_pooled.py"
        )
    data = np.load(path)
    scores = data["scores"]
    return {
        "scores": scores,
        "scores_2d": scores.reshape(16, 64),
        "mask_1": data["mask_keep_1_0"].reshape(16, 64),
        "mask_05": data["mask_keep_0_5"].reshape(16, 64),
        "mask_0125": data["mask_keep_0_125"].reshape(16, 64),
    }


def load_baseline_systems() -> list[dict]:
    """Deployment-class baselines with accuracy, latency, energy where measured."""
    arm = _load_json("results/baselines/arm_hdc_results.json")
    mlp = _load_json("results/baselines/mlp_results.json")
    silicon = load_measured_silicon()
    pl = next(p for p in silicon if p["anchor"] == "A")
    arm_e = next(p for p in silicon if p["anchor"] == "ARM")
    return [
        {
            "name": "PL DMA\n(batch)",
            "acc": pl["acc"],
            "lat_us": 4.0,
            "uj": pl["uj"],
            "uj_std": pl["uj_std"],
            "train": "none",
            "color": "#4c78a8",
        },
        {
            "name": "ARM HDC\n(PS)",
            "acc": 100.0 * arm["meta"]["spatial_mean_accuracy"],
            "lat_us": 819.0,
            "uj": arm_e["uj"],
            "uj_std": arm_e["uj_std"],
            "train": "none",
            "color": "#e15759",
        },
        {
            "name": "MLP\nint8",
            "acc": 100.0 * mlp["meta"]["spatial_mean_accuracy_int8"],
            "lat_us": None,
            "uj": None,
            "uj_std": None,
            "train": "25 ep",
            "color": "#59a14f",
        },
    ]


# Device post-route utilisation (Phase 3 bitstream, README).
DEPLOY_LUTS = 35206
DEVICE_LUT_BUDGET = 53200
# --------------------------------------------------------------------------- #
def fig_per_subject(d: dict, out: Path) -> None:
    subs = d["subjects"] + ["Mean"]
    hdc = d["hdc"] + [d["hdc_mean"]]
    mlp = d["mlp"] + [d["mlp_mean"]]
    x = np.arange(len(subs))
    w = 0.38

    fig, ax = plt.subplots(figsize=(3.5, 2.2) if PAPER_MODE else (8.5, 4.8))
    ax.bar(x - w / 2, hdc, w, label="ARM HDC ref (host sim)", color="#4c78a8")
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
    # CNT_W=4/5/6 are identical in sweep — collapse to two legend entries.
    by_curve: dict[tuple[float, ...], list[int]] = {}
    for c in cnts:
        ys = tuple(next(r["acc"] for r in keep1 if r["D"] == D and r["cnt_w"] == c) for D in Ds)
        by_curve.setdefault(ys, []).append(c)
    for ys, cs in by_curve.items():
        lo, hi = min(cs), max(cs)
        label = f"CNT_W={lo}" if lo == hi else f"CNT_W={lo}–{hi}"
        style = "o--" if lo == 3 else "o-"
        ax.plot([str(D) for D in Ds], list(ys), style, lw=1.6, ms=5, label=label)
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
            label="Python energy proxy (% of full)")
    ax.set_xlabel("Bits pruned (%) — informed Fisher mask")
    ax.set_ylabel("Percent")
    ax.set_ylim(0, 100)
    ax.set_title("Hook A — pruning is free @ D=1024 (Python sweep)")
    ax.legend(loc="center left", fontsize=8)
    ax.text(
        0.98,
        0.05,
        "Energy line = Python dynamic proxy (8×↓ at keep=0.125).\n"
        "Measured PL J21 batch ≈ flat ~12 µJ (static-dominated).",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="0.35",
    )
    _save(fig, out, "hookA_pruning")


def fig_hook_a_pareto_measured(rows: list[dict], silicon: list[dict], out: Path) -> None:
    """Hook A Pareto: Python area ladder + measured silicon energy at D=1024 anchors."""
    ladder = sorted(
        (r for r in rows if r["cnt_w"] == 6 and r["keep"] == 1.0), key=lambda r: r["luts"]
    )
    pl = [p for p in silicon if p["path"] == "PL"]
    arm = next(p for p in silicon if p["path"] == "ARM")

    if PAPER_MODE:
        fig, axes = plt.subplots(1, 2, figsize=(IEEE_COL_W, 1.75))
        fig.subplots_adjust(wspace=0.42)
    else:
        fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))

    luts_k = [r["luts"] / 1000 for r in ladder]
    acc_py = [r["acc"] for r in ladder]
    py_label = "Python OOC" if PAPER_MODE else "Python sweep (CNT_W=6, keep=1.0)"
    ann_fs = 5 if PAPER_MODE else 7

    # --- (a) Accuracy vs OOC slice LUTs ---
    ax = axes[0]
    ax.plot(luts_k, acc_py, "o-", color="#4c78a8", lw=1.2, ms=3 if PAPER_MODE else 6, label=py_label)
    if PAPER_MODE:
        for r in ladder:
            if r["D"] in (1024, 2048):
                ax.annotate(
                    f"D={r['D']}",
                    xy=(r["luts"] / 1000, r["acc"]),
                    xytext=(4, -7 if r["D"] == 1024 else 5),
                    textcoords="offset points",
                    fontsize=ann_fs,
                    color="#b4413c" if r["D"] == 2048 else "0.35",
                )
    else:
        for r in ladder:
            over = r["luts"] > DEVICE_LUT_BUDGET
            ax.annotate(
                f"D={r['D']}",
                xy=(r["luts"] / 1000, r["acc"]),
                xytext=(3, -9 if not over else 3),
                textcoords="offset points",
                fontsize=ann_fs,
                color="#b4413c" if over else "0.25",
            )
    d1024 = next(r for r in ladder if r["D"] == 1024)
    sil_label = "Silicon" if PAPER_MODE else f"Silicon EMG @ D=1024 ({DEPLOY_LUTS // 1000}k LUT, placed)"
    ax.scatter(
        [DEPLOY_LUTS / 1000],
        [pl[0]["acc"] if pl else d1024["acc"]],
        s=55 if PAPER_MODE else 120,
        c="#e15759",
        marker="*",
        zorder=5,
        label=sil_label,
    )
    ax.axvline(DEVICE_LUT_BUDGET / 1000, color="#b4413c", ls="--", lw=0.7, alpha=0.65)
    if PAPER_MODE:
        ax.text(
            DEVICE_LUT_BUDGET / 1000,
            59.5,
            "LUT\nbudget",
            rotation=90,
            va="bottom",
            ha="center",
            fontsize=5,
            color="#b4413c",
        )
    else:
        ax.text(
            DEVICE_LUT_BUDGET / 1000 - 0.8,
            60.5,
            "xc7z020\nLUT budget",
            rotation=90,
            va="bottom",
            ha="right",
            fontsize=7,
            color="#b4413c",
        )
    ax.set_xlabel("LUTs (k)" if PAPER_MODE else "Slice LUTs (thousands) — curve: OOC estimate; *: placed post-route")
    ax.set_ylabel("Accuracy (%)" if PAPER_MODE else "Spatial / board accuracy (%)")
    set_figure_title(ax, "(a)", "(a) Accuracy vs area — Python OOC sweep + placed silicon")
    ax.legend(loc="lower right", fontsize=5 if PAPER_MODE else 7, frameon=False)
    ax.set_ylim(58, 80 if PAPER_MODE else 82)
    ax.tick_params(labelsize=6 if PAPER_MODE else 9)
    if not PAPER_MODE:
        ax.text(
            0.02,
            0.02,
            "Blue line: Python spatial mean (OOC LUTs).\n"
            f"Red *: board EMG replay @ D=1024 ({DEPLOY_LUTS // 1000}k placed LUTs).",
            transform=ax.transAxes,
            fontsize=7,
            va="bottom",
            color="0.35",
        )

    # --- (b) Measured energy at D=1024 anchors ---
    ax = axes[1]
    for p in pl:
        ax.errorbar(
            p["uj"],
            p["acc"],
            xerr=p["uj_std"],
            fmt="o",
            ms=4 if PAPER_MODE else 8,
            capsize=1.5 if PAPER_MODE else 3,
            color="#4c78a8",
            label="PL DMA batch" if p["anchor"] == "A" and not PAPER_MODE else None,
        )
        if PAPER_MODE:
            ax.annotate(
                p["anchor"],
                xy=(p["uj"], p["acc"]),
                xytext=(2, 2),
                textcoords="offset points",
                fontsize=5,
            )
        else:
            ax.annotate(
                f"{p['anchor']} (keep={p['keep']})",
                xy=(p["uj"], p["acc"]),
                xytext=(8, 6),
                textcoords="offset points",
                fontsize=7,
            )
    ax.errorbar(
        arm["uj"],
        arm["acc"],
        xerr=arm["uj_std"],
        fmt="s",
        ms=4 if PAPER_MODE else 8,
        capsize=1.5 if PAPER_MODE else 3,
        color="#e15759",
        label="ARM" if PAPER_MODE else "ARM PS software",
    )
    if not PAPER_MODE:
        ax.annotate(
            "ARM (host acc)",
            xy=(arm["uj"], arm["acc"]),
            xytext=(8, -10),
            textcoords="offset points",
            fontsize=7,
        )
    ax.set_xscale("log")
    ax.set_xlabel("Energy (µJ/w)" if PAPER_MODE else "Measured total energy (µJ/window, J21 batch)")
    ax.set_ylabel("Accuracy (%)" if PAPER_MODE else "Board / baseline accuracy (%)")
    set_figure_title(ax, "(b)", "(b) Measured energy — flat PL, ARM ~175× (static-dominated PL)")
    if PAPER_MODE:
        ax.legend(loc="lower left", fontsize=5, frameon=False, handles=[
            plt.Line2D([0], [0], marker="o", color="#4c78a8", ls="", ms=4, label="PL"),
            plt.Line2D([0], [0], marker="s", color="#e15759", ls="", ms=4, label="ARM"),
        ])
    else:
        ax.legend(loc="lower left", fontsize=7)
    ax.set_ylim(73.85, 74.45 if PAPER_MODE else 74.6)
    ax.tick_params(labelsize=6 if PAPER_MODE else 9)
    if not PAPER_MODE:
        ax.text(
            0.02,
            0.02,
            "PL A/B/C: board EMG replay, Fisher keep 1.0 / 0.5 / 0.125.\n"
            "Acc flat; J21 energy ≈ static × batch slot (~12 µJ).\n"
            "ARM acc = host libhdc_arm_ref (no full board EMG replay).",
            transform=ax.transAxes,
            fontsize=7,
            va="bottom",
            color="0.35",
        )

    if not PAPER_MODE:
        fig.suptitle(
            "Hook A Pareto — Python design space and measured ZedBoard anchors (2026-07)",
            fontsize=11,
            y=1.02,
        )
    _save(fig, out, "hookA_pareto_measured")


def fig_fisher_heatmap(fisher: dict, out: Path) -> None:
    """Pooled Fisher scores + informed keep masks (silicon mask layout 16×64 bits)."""
    scores = fisher["scores_2d"]
    rank = np.argsort(-fisher["scores"])
    ranked = fisher["scores"][rank]
    n_nonzero = int((fisher["scores"] > 0).sum())

    if PAPER_MODE:
        fig = plt.figure(figsize=(IEEE_COL_W, 2.15))
        gs = fig.add_gridspec(2, 2, height_ratios=[1.05, 0.95], hspace=0.55, wspace=0.4)
        axes = np.array([[fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])],
                         [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]])
        tick_fs = 5
    else:
        fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.5), gridspec_kw={"height_ratios": [1.2, 1]})
        tick_fs = 9

    ax = axes[0, 0]
    im = ax.imshow(scores, aspect="auto", cmap="viridis", interpolation="nearest")
    set_figure_title(ax, "(a)", "(a) Pooled Fisher score (TRAIN, 5 subjects)")
    ax.set_xlabel("Bit" if PAPER_MODE else "Bit index within 64-bit word")
    ax.set_ylabel("Word" if PAPER_MODE else "Word index (0–15)")
    if PAPER_MODE:
        ax.set_xticks([0, 32, 63])
        ax.set_yticks([0, 8, 15])
        ax.tick_params(labelsize=tick_fs)
        cbar = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.04)
        cbar.ax.tick_params(labelsize=5, length=2)
        cbar.set_label("Score", fontsize=5)
    else:
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Fisher score")

    ax = axes[0, 1]
    ax.plot(np.arange(1, 1025), ranked, color="#4c78a8", lw=1.0 if PAPER_MODE else 1.2)
    ax.axvline(512, color="#f28e2b", ls="--", lw=0.9)
    ax.axvline(128, color="#e15759", ls="--", lw=0.9)
    if not PAPER_MODE:
        ax.axvline(n_nonzero + 0.5, color="0.55", ls=":", lw=0.9, label=f"score=0 after rank {n_nonzero}")
        ax.legend(fontsize=7, loc="upper right")
    elif PAPER_MODE:
        ax.text(135, ranked[127] * 0.92, "0.125", fontsize=5, color="#e15759", ha="left")
        ax.text(520, ranked[511] * 0.92, "0.5", fontsize=5, color="#f28e2b", ha="left")
    ax.set_xlabel("Rank" if PAPER_MODE else "Rank (1 = highest Fisher score)")
    ax.set_ylabel("Score" if PAPER_MODE else "Fisher score")
    set_figure_title(ax, "(b)", "(b) Score rank — anchor cutoffs")
    ax.set_xlim(1, 1024)
    if PAPER_MODE:
        ax.tick_params(labelsize=tick_fs)

    masks = [
        ("(c)", "(c) Informed mask @ keep=0.5", fisher["mask_05"], "#f28e2b", "B"),
        ("(d)", "(d) Informed mask @ keep=0.125", fisher["mask_0125"], "#e15759", "C"),
    ]
    for ax, (panel, title, mask, edge, anchor) in zip(axes[1], masks):
        ax.imshow(mask, aspect="auto", cmap="gray_r", vmin=0, vmax=1, interpolation="nearest")
        set_figure_title(ax, panel, title)
        ax.set_xlabel("Bit" if PAPER_MODE else "Bit in word")
        ax.set_ylabel("Word")
        if PAPER_MODE:
            ax.set_xticks([])
            ax.set_yticks([0, 15])
            ax.tick_params(labelsize=tick_fs)
            ax.text(
                0.03,
                0.97,
                f"Anchor {anchor}",
                transform=ax.transAxes,
                fontsize=5,
                va="top",
                ha="left",
                color="0.35",
            )
        else:
            n_keep = int(mask.sum())
            tie_note = ""
            if n_keep == 512:
                tie_note = f"\n{512 - n_nonzero} zero-score bits by index order"
            ax.text(
                0.02,
                0.98,
                f"keep {n_keep}/1024 ({100.0 * n_keep / 1024:.1f}%){tie_note}",
                transform=ax.transAxes,
                va="top",
                fontsize=8,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
            )
            for spine in ax.spines.values():
                spine.set_edgecolor(edge)
                spine.set_linewidth(2)

    if not PAPER_MODE:
        fig.suptitle(
            "Fisher-informed pruning masks — pooled TRAIN (same method as silicon anchors B/C)",
            fontsize=11,
            y=1.02,
        )
        fig.text(
            0.5,
            -0.02,
            f"{n_nonzero}/1024 bits have Fisher score > 0; "
            "keep=0.5 mask (c) fills remainder at score=0 by bit index. "
            "Mask (d) matches silicon anchor C bitstream.",
            ha="center",
            fontsize=8,
            color="0.4",
        )
    _save(fig, out, "fisher_heatmap")


def fig_baselines_bar(systems: list[dict], out: Path) -> None:
    """Accuracy, latency, and measured energy for PL vs ARM vs MLP."""
    names = [s["name"] for s in systems]
    tick = _paper_tick_labels(names) if PAPER_MODE else names
    colors = [s["color"] for s in systems]
    fs = 5 if PAPER_MODE else 7

    if PAPER_MODE:
        fig, axes = plt.subplots(1, 3, figsize=(IEEE_COL_W, 1.55))
        fig.subplots_adjust(wspace=0.62)
    else:
        fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.5))

    # (a) Accuracy — all three systems
    ax = axes[0]
    x = np.arange(len(names))
    acc = [s["acc"] for s in systems]
    bars = ax.bar(x, acc, color=colors, width=0.58, edgecolor="0.2", linewidth=0.5)
    if PAPER_MODE:
        ax.axhline(74.15, color="0.65", ls=":", lw=0.7, zorder=0)
    else:
        ax.axhline(74.15, color="0.5", ls=":", lw=0.9, label="Hook A Python ref (74.15%)")
    ax.set_xticks(x, tick, fontsize=fs)
    ax.set_ylabel("Acc. (%)" if PAPER_MODE else "Spatial / board accuracy (%)")
    ax.set_ylim(70, 98 if PAPER_MODE else 96)
    set_figure_title(ax, "(a)", "(a) Accuracy")
    if not PAPER_MODE:
        ax.legend(fontsize=fs, loc="upper left")
    for bar, v in zip(bars, acc):
        if PAPER_MODE and v < 80:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                v - 2.5,
                f"{v:.1f}",
                ha="center",
                va="top",
                fontsize=fs,
                color="white",
                fontweight="bold",
            )
        else:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                v + 0.6,
                f"{v:.1f}",
                ha="center",
                fontsize=fs,
            )
    if PAPER_MODE:
        ax.tick_params(axis="y", labelsize=fs)

    # (b) Latency — PL and ARM only
    ax = axes[1]
    lat_names = [s["name"] for s in systems if s["lat_us"] is not None]
    lat_tick = _paper_tick_labels(lat_names) if PAPER_MODE else lat_names
    lat_vals = [s["lat_us"] for s in systems if s["lat_us"] is not None]
    lat_colors = [s["color"] for s in systems if s["lat_us"] is not None]
    xl = np.arange(len(lat_names))
    ax.bar(xl, lat_vals, color=lat_colors, width=0.52, edgecolor="0.2", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_xticks(xl, lat_tick, fontsize=fs)
    ax.set_ylabel("µs (log)" if PAPER_MODE else "Latency (µs/window, log)")
    set_figure_title(ax, "(b)", "(b) On-board latency")
    for i, v in enumerate(lat_vals):
        ax.text(i, v * 1.15, f"{v:.0f}", ha="center", fontsize=fs)
    if not PAPER_MODE:
        ax.text(0.98, 0.05, "MLP: not on-board", transform=ax.transAxes, ha="right", fontsize=7, color="0.45")
    if PAPER_MODE:
        ax.tick_params(axis="y", labelsize=fs)

    # (c) Energy — PL and ARM only
    ax = axes[2]
    en_names = [s["name"] for s in systems if s["uj"] is not None]
    en_tick = _paper_tick_labels(en_names) if PAPER_MODE else en_names
    en_vals = [s["uj"] for s in systems if s["uj"] is not None]
    en_std = [s["uj_std"] for s in systems if s["uj"] is not None]
    en_colors = [s["color"] for s in systems if s["uj"] is not None]
    xe = np.arange(len(en_names))
    ax.bar(
        xe,
        en_vals,
        yerr=en_std,
        capsize=1.5 if PAPER_MODE else 4,
        color=en_colors,
        width=0.52,
        edgecolor="0.2",
        linewidth=0.5,
        error_kw={"elinewidth": 0.7 if PAPER_MODE else 1.0},
    )
    ax.set_yscale("log")
    ax.set_xticks(xe, en_tick, fontsize=fs)
    ax.set_ylabel("µJ (log)" if PAPER_MODE else "Total energy (µJ/window, J21 log)")
    set_figure_title(ax, "(c)", "(c) Measured batch energy")
    for i, v in enumerate(en_vals):
        ax.text(i, v * 1.22, f"{v:.0f}", ha="center", fontsize=fs)
    if not PAPER_MODE:
        ax.text(0.98, 0.05, "MLP: not measured", transform=ax.transAxes, ha="right", fontsize=7, color="0.45")
    if PAPER_MODE:
        ax.tick_params(axis="y", labelsize=fs)

    if not PAPER_MODE:
        fig.suptitle(
            "Comparison baselines — P-may2026, 5 subjects (HDC vs MLP deployment class)",
            fontsize=11,
            y=1.04,
        )
        fig.text(
            0.5,
            -0.02,
            "PL acc: board EMG replay · ARM acc: host libhdc_arm_ref sim · "
            "PL/ARM latency & energy: measured on ZedBoard (INA219 J21)",
            ha="center",
            fontsize=8,
            color="0.4",
        )
    _save(fig, out, "baselines_bar")


def load_twist1(rel: str = "results/twist1/twist1_results.json") -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fig_twist1(data: dict, out: Path, name: str = "twist1_informed_vs_random") -> None:
    """Twist 1 — Fisher informed vs random mask at identical keep ratio (D=1024)."""
    meta = data["meta"]
    rows = data["per_subject"]
    subs = [f"S{r['subject']}" for r in rows]
    x = np.arange(len(subs))
    w = 0.36
    informed = [100.0 * r["informed_accuracy"] for r in rows]
    random_m = [100.0 * r["random_accuracy_mean"] for r in rows]
    mean_gap = meta["mean_gap_pp"]
    target = meta.get("target_gap_pp", 5.0)

    fig, ax = plt.subplots(figsize=(3.5, 2.2) if PAPER_MODE else (8.5, 4.8))
    ax.bar(x - w / 2, informed, w, label="Fisher informed", color="#4c78a8")
    ax.bar(x + w / 2, random_m, w, label="Random (mean over seeds)", color="#e15759")
    for i, (inf, rnd) in enumerate(zip(informed, random_m)):
        ax.text(i - w / 2, inf + 0.3, f"{inf:.1f}", ha="center", va="bottom", fontsize=7)
        ax.text(i + w / 2, rnd + 0.3, f"{rnd:.1f}", ha="center", va="bottom", fontsize=7)
        ax.text(i, max(inf, rnd) + 2.0, f"Δ{inf - rnd:+.1f}", ha="center", fontsize=7, color="0.35")
    ax.set_xticks(x, subs)
    ax.set_ylabel("Spatial accuracy (%)")
    ax.set_ylim(55, 85)
    if PAPER_MODE:
        ax.set_title("")
    else:
        ax.set_title(
            f"Twist 1 — informed vs random @ keep={meta['keep_ratio']} "
            f"(D={meta['D']}, CNT_W={meta['cnt_w']})"
        )
    ax.legend(loc="lower left", fontsize=8)
    ax.text(
        0.98,
        0.98,
        f"Mean gap: {mean_gap:+.2f} pp\nTarget: ≥ {target:.0f} pp",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )
    if not PAPER_MODE:
        fig.suptitle(
            "Twist 1 — bit selection matters at iso-density (per-subject Fisher masks)",
            fontsize=11,
            y=1.02,
        )
    _save(fig, out, name)


def load_twist2(path: str = "results/twist2/twist2_results.json") -> dict | None:
    p = REPO / path
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def fig_twist2(
    data: dict,
    out: Path,
    name: str = "twist2_cross_subject",
    ylim: tuple[float, float] | None = None,
) -> None:
    """Twist 2 — local oracle vs pooled cross-subject mask on held-out subjects."""
    meta = data["meta"]
    result = data["result"]
    rows = result["per_test_subject"]
    subs = [f"S{r['subject']}" for r in rows]
    x = np.arange(len(subs))
    w = 0.36
    local = [100.0 * r["local_oracle_accuracy"] for r in rows]
    pooled = [100.0 * r["pooled_transfer_accuracy"] for r in rows]
    mean_gap = result["mean_gap_local_minus_pooled_pp"]
    target = meta.get("target_gap_pp", 3.0)
    train_s = ",".join(str(s) for s in result["train_subjects"])
    n = len(subs)
    if PAPER_MODE:
        fig_w, fig_h = IEEE_COL_W, 2.1
        legend_train = f"Pooled transfer (train S{result['train_subjects'][0]}--{result['train_subjects'][-1]})"
    else:
        fig_w = max(8.5, 0.48 * n + 2.5)
        fig_h = 4.8
        legend_train = f"Pooled transfer (train S{train_s})"

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    annotate = len(subs) <= 6
    ax.bar(x - w / 2, local, w, label="Local oracle (own-subject mask)", color=PAPER_COLORS["blue"])
    ax.bar(x + w / 2, pooled, w, label=legend_train, color=PAPER_COLORS["green"])
    if annotate:
        for i, (loc, pool) in enumerate(zip(local, pooled)):
            ax.text(i - w / 2, loc + 0.3, f"{loc:.1f}", ha="center", va="bottom", fontsize=7)
            ax.text(i + w / 2, pool + 0.3, f"{pool:.1f}", ha="center", va="bottom", fontsize=7)
            ax.text(i, max(loc, pool) + 2.0, f"Δ{loc - pool:+.1f}", ha="center", fontsize=7, color="0.35")
    ax.set_xticks(x, subs)
    if not annotate:
        ax.tick_params(axis="x", rotation=45, labelsize=6 if PAPER_MODE else 9)
        for label in ax.get_xticklabels():
            label.set_ha("right")
    ax.set_ylabel("Spatial accuracy (%)")
    vals = local + pooled
    if ylim is None:
        lo = max(0, min(vals) - 5)
        hi = min(100, max(vals) + 8)
        ax.set_ylim(lo, hi)
    else:
        ax.set_ylim(*ylim)
    if PAPER_MODE:
        ax.set_title("")
    else:
        ax.set_title(
            f"Twist 2 — cross-subject mask @ keep={result['keep_ratio']} "
            f"(D={result['D']}, CNT_W={result['cnt_w']})"
        )
    ax.legend(loc="lower left", fontsize=7 if PAPER_MODE else 8)
    verdict = "generalises" if meta.get("generalises") else "per-subject cal."
    ax.text(
        0.98,
        0.98,
        f"Mean gap: {mean_gap:+.2f} pp\nTarget |gap| ≤ {target:.0f} pp → {verdict}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7 if PAPER_MODE else 8,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )
    if not PAPER_MODE:
        fig.suptitle(
            "Twist 2 — pooled Fisher mask trained on subject subset, tested on held-out subjects",
            fontsize=11,
            y=1.02,
        )
    _save(fig, out, name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/figures", help="output dir (rel to repo root)")
    ap.add_argument("--dpi", type=int, default=PAPER_DPI, help="PNG/PDF rasterization DPI")
    ap.add_argument("--show", action="store_true", help="also open interactive windows")
    ap.add_argument(
        "--paper",
        action="store_true",
        help="compact IEEE single-column export: no suptitles, panel labels only",
    )
    args = ap.parse_args()

    global PAPER_MODE
    PAPER_MODE = args.paper

    apply_paper_style(dpi=args.dpi, paper=args.paper)

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
    fig_hook_a_pareto_measured(hook, load_measured_silicon(), out)
    fig_fisher_heatmap(load_fisher_pooled(), out)
    fig_baselines_bar(load_baseline_systems(), out)
    twist1 = load_twist1()
    if twist1:
        fig_twist1(twist1, out)
    else:
        print("  skip twist1_informed_vs_random (missing results/twist1/twist1_results.json)")
    twist1_aggressive = load_twist1("results/twist1_keep0125/twist1_results.json")
    if twist1_aggressive:
        fig_twist1(
            twist1_aggressive,
            out,
            name="twist1_informed_vs_random_keep0125",
        )
    else:
        print("  skip twist1 keep=0.125 figure (missing results/twist1_keep0125/)")
    twist2 = load_twist2()
    if twist2:
        fig_twist2(twist2, out)
    else:
        print("  skip twist2_cross_subject (missing results/twist2/twist2_results.json)")
    twist2_36 = load_twist2("results/twist2_36/twist2_results.json")
    if twist2_36:
        fig_twist2(twist2_36, out, name="twist2_cross_subject_36")
    else:
        print("  skip twist2_cross_subject_36 (missing results/twist2_36/)")

    if args.show:
        plt.show()
    print("Done.")


if __name__ == "__main__":
    main()
