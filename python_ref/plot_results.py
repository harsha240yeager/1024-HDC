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


def fig_hook_a_pareto_measured(rows: list[dict], silicon: list[dict], out: Path) -> None:
    """Hook A Pareto: Python area ladder + measured silicon energy at D=1024 anchors."""
    ladder = sorted(
        (r for r in rows if r["cnt_w"] == 6 and r["keep"] == 1.0), key=lambda r: r["luts"]
    )
    pl = [p for p in silicon if p["path"] == "PL"]
    arm = next(p for p in silicon if p["path"] == "ARM")

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))

    # --- (a) Accuracy vs OOC slice LUTs (D sweep) + deployed D=1024 ---
    ax = axes[0]
    luts_k = [r["luts"] / 1000 for r in ladder]
    acc_py = [r["acc"] for r in ladder]
    ax.plot(luts_k, acc_py, "o-", color="#4c78a8", lw=1.6, ms=6, label="Python sweep (CNT_W=6, keep=1.0)")
    for r in ladder:
        over = r["luts"] > DEVICE_LUT_BUDGET
        ax.annotate(
            f"D={r['D']}",
            xy=(r["luts"] / 1000, r["acc"]),
            xytext=(5, -12 if not over else 5),
            textcoords="offset points",
            fontsize=7,
            color="#b4413c" if over else "0.25",
        )
    d1024 = next(r for r in ladder if r["D"] == 1024)
    ax.scatter(
        [DEPLOY_LUTS / 1000],
        [pl[0]["acc"] if pl else d1024["acc"]],
        s=120,
        c="#e15759",
        marker="*",
        zorder=5,
        label=f"Silicon EMG @ D=1024 ({DEPLOY_LUTS // 1000}k LUT, placed)",
    )
    ax.axvline(DEVICE_LUT_BUDGET / 1000, color="#b4413c", ls="--", lw=0.9, alpha=0.7)
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
    ax.set_xlabel("Slice LUTs (thousands)")
    ax.set_ylabel("Spatial / board accuracy (%)")
    ax.set_title("(a) Accuracy vs area — D sweep + deployed bitstream")
    ax.legend(loc="lower right", fontsize=7)
    ax.set_ylim(58, 82)

    # --- (b) Measured energy at D=1024 anchors (board accuracy) ---
    ax = axes[1]
    for p in pl:
        ax.errorbar(
            p["uj"],
            p["acc"],
            xerr=p["uj_std"],
            fmt="o",
            ms=8,
            capsize=3,
            color="#4c78a8",
            label="PL DMA batch" if p["anchor"] == "A" else None,
        )
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
        ms=8,
        capsize=3,
        color="#e15759",
        label="ARM PS software",
    )
    ax.annotate(
        "ARM",
        xy=(arm["uj"], arm["acc"]),
        xytext=(8, -10),
        textcoords="offset points",
        fontsize=7,
    )
    # Python proxy at D=1024 (CNT_W=6) — same accuracy, scaled proxy on secondary axis note
    proxy_pts = sorted(
        (r for r in rows if r["D"] == 1024 and r["cnt_w"] == 6),
        key=lambda r: r["keep"],
        reverse=True,
    )
    ax2 = ax.twiny()
    proxy_x = [p["uj"] for p in pl if p["anchor"] == "A"]
    if proxy_x:
        base_uj = proxy_x[0]
        ax2.set_xlim(ax.get_xlim())
        for r in proxy_pts:
            px = base_uj * r["energy"]  # energy_proxy_d_keep at D=1024
            ax2.axvline(px, color="0.75", ls=":", lw=0.8)
        ax2.set_xlabel("Python energy proxy × anchor-A µJ (dashed)", fontsize=8, color="0.45")
        ax2.tick_params(axis="x", labelsize=7, colors="0.45")
    ax.set_xscale("log")
    ax.set_xlabel("Measured total energy (µJ/window, J21 batch)")
    ax.set_ylabel("Board / baseline accuracy (%)")
    ax.set_title("(b) Measured energy — flat PL, ARM ~175× (static-dominated PL)")
    ax.legend(loc="lower left", fontsize=7)
    ax.set_ylim(73.8, 74.6)
    ax.text(
        0.02,
        0.02,
        "PL A/B/C: informed Fisher keep 1.0 / 0.5 / 0.125\n"
        "Accuracy flat; J21 energy ≈ static × batch slot",
        transform=ax.transAxes,
        fontsize=7,
        va="bottom",
        color="0.35",
    )

    fig.suptitle(
        "Hook A Pareto — Python design space and measured ZedBoard anchors (2026-07)",
        fontsize=11,
        y=1.02,
    )
    _save(fig, out, "hookA_pareto_measured")


def fig_fisher_heatmap(fisher: dict, out: Path) -> None:
    """Pooled Fisher scores + informed keep masks (silicon mask layout 16×64 bits)."""
    scores = fisher["scores_2d"]
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 6.5), gridspec_kw={"height_ratios": [1.2, 1]})

    ax = axes[0, 0]
    im = ax.imshow(scores, aspect="auto", cmap="viridis", interpolation="nearest")
    ax.set_title("(a) Pooled Fisher score (TRAIN, 5 subjects)")
    ax.set_xlabel("Bit index within 64-bit word")
    ax.set_ylabel("Word index (0–15)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Fisher score")

    ax = axes[0, 1]
    rank = np.argsort(-fisher["scores"])
    ax.plot(np.arange(1, 1025), fisher["scores"][rank], color="#4c78a8", lw=1.2)
    ax.axvline(512, color="#f28e2b", ls="--", lw=1, label="keep=0.5 (512 bits)")
    ax.axvline(128, color="#e15759", ls="--", lw=1, label="keep=0.125 (128 bits)")
    ax.set_xlabel("Rank (1 = highest Fisher score)")
    ax.set_ylabel("Fisher score")
    ax.set_title("(b) Score rank — anchor cutoffs")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_xlim(1, 1024)

    masks = [
        ("(c) Informed mask @ keep=0.5", fisher["mask_05"], "#f28e2b"),
        ("(d) Informed mask @ keep=0.125", fisher["mask_0125"], "#e15759"),
    ]
    for ax, (title, mask, edge) in zip(axes[1], masks):
        ax.imshow(mask, aspect="auto", cmap="gray_r", vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(title)
        ax.set_xlabel("Bit in word")
        ax.set_ylabel("Word")
        n_keep = int(mask.sum())
        ax.text(
            0.02,
            0.98,
            f"keep {n_keep}/1024 ({100.0 * n_keep / 1024:.1f}%)",
            transform=ax.transAxes,
            va="top",
            fontsize=8,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )
        for spine in ax.spines.values():
            spine.set_edgecolor(edge)
            spine.set_linewidth(2)

    fig.suptitle(
        "Fisher-informed pruning masks — pooled TRAIN (same method as silicon anchors B/C)",
        fontsize=11,
        y=1.02,
    )
    _save(fig, out, "fisher_heatmap")


def fig_baselines_bar(systems: list[dict], out: Path) -> None:
    """Accuracy, latency, and measured energy for PL vs ARM vs MLP."""
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.0))
    names = [s["name"] for s in systems]
    x = np.arange(len(names))
    colors = [s["color"] for s in systems]

    ax = axes[0]
    acc = [s["acc"] for s in systems]
    bars = ax.bar(x, acc, color=colors, width=0.55, edgecolor="0.2", linewidth=0.6)
    ax.axhline(74.15, color="0.5", ls=":", lw=0.9, label="Hook A Python ref (74.15%)")
    ax.set_xticks(x, names, fontsize=8)
    ax.set_ylabel("Spatial / board accuracy (%)")
    ax.set_ylim(70, 96)
    ax.set_title("(a) Accuracy")
    ax.legend(fontsize=7, loc="upper left")
    for bar, v in zip(bars, acc):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.4, f"{v:.2f}%", ha="center", fontsize=7)

    ax = axes[1]
    lat_names = [s["name"] for s in systems if s["lat_us"] is not None]
    lat_vals = [s["lat_us"] for s in systems if s["lat_us"] is not None]
    lat_colors = [s["color"] for s in systems if s["lat_us"] is not None]
    xl = np.arange(len(lat_names))
    ax.bar(xl, lat_vals, color=lat_colors, width=0.5, edgecolor="0.2", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_xticks(xl, lat_names, fontsize=8)
    ax.set_ylabel("Latency (µs/window, log)")
    ax.set_title("(b) On-board latency")
    for i, v in enumerate(lat_vals):
        ax.text(i, v * 1.15, f"{v:.0f} µs", ha="center", fontsize=7)
    ax.text(0.98, 0.05, "MLP: not on-board", transform=ax.transAxes, ha="right", fontsize=7, color="0.45")

    ax = axes[2]
    en_names = [s["name"] for s in systems if s["uj"] is not None]
    en_vals = [s["uj"] for s in systems if s["uj"] is not None]
    en_std = [s["uj_std"] for s in systems if s["uj"] is not None]
    en_colors = [s["color"] for s in systems if s["uj"] is not None]
    xe = np.arange(len(en_names))
    ax.bar(xe, en_vals, yerr=en_std, capsize=4, color=en_colors, width=0.5, edgecolor="0.2", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_xticks(xe, en_names, fontsize=8)
    ax.set_ylabel("Total energy (µJ/window, J21 log)")
    ax.set_title("(c) Measured batch energy")
    for i, v in enumerate(en_vals):
        ax.text(i, v * 1.25, f"{v:.1f}", ha="center", fontsize=7)
    ax.text(0.98, 0.05, "MLP: not measured", transform=ax.transAxes, ha="right", fontsize=7, color="0.45")

    fig.suptitle(
        "Comparison baselines — P-may2026, 5 subjects (HDC vs MLP deployment class)",
        fontsize=11,
        y=1.02,
    )
    _save(fig, out, "baselines_bar")


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
    fig_hook_a_pareto_measured(hook, load_measured_silicon(), out)
    fig_fisher_heatmap(load_fisher_pooled(), out)
    fig_baselines_bar(load_baseline_systems(), out)

    if args.show:
        plt.show()
    print("Done.")


if __name__ == "__main__":
    main()
