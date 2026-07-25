#!/usr/bin/env python3
"""Verify every headline number in the DATE manuscript against committed artifacts.

Each claim below names where it appears in the paper, the value the paper
prints, and the committed result file it must come from. Run this after any
rerun to catch a stale figure before a reviewer does.

Standard library only, so it works in a bare clone with no dependencies:

    python3 scripts/check_paper_numbers.py
    python3 scripts/check_paper_numbers.py --markdown
    python3 scripts/check_paper_numbers.py --json results/repro/claim_check.json

Exit code is 0 when every claim passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Artifact readers
# --------------------------------------------------------------------------


def read_text(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(rel: str):
    return json.loads(read_text(rel))


def load_csv(rel: str) -> list[dict]:
    return list(csv.DictReader(read_text(rel).splitlines()))


def board_accuracy(rel: str) -> float:
    """Pull the replay accuracy out of a ZedBoard board_emg_replay.txt log."""
    matches = re.findall(r"accuracy=([0-9.]+)%", read_text(rel))
    if not matches:
        raise ValueError(f"no accuracy line in {rel}")
    return float(matches[-1])


def energy_total(anchor: str) -> float:
    """Total uJ/window for one anchor from the INA219 campaign summary."""
    current = None
    for line in read_text("results/phase3/energy_summary.txt").splitlines():
        header = re.match(r"Anchor (\S+)", line.strip())
        if header:
            current = header.group(1)
        total = re.search(r"Total \([^)]*\):\s*([0-9.]+)", line)
        if total and current == anchor:
            return float(total.group(1))
    raise ValueError(f"no Total row for anchor {anchor}")


def batch_latency_us(anchor: str) -> float:
    """Per-window batch latency (us) from an INA219 run: duration / window count.

    The on-board bench prints total/N with integer division, so read the raw
    duration instead of trusting the rounded per-window line in the log.
    """
    text = read_text(f"results/phase3/energy_runs/anchor_{anchor}/run01/energy_batch.txt")
    ms = re.search(r"Batch duration \(ms\):\s*([0-9.]+)", text)
    windows = re.search(r"Batch windows:\s*([0-9]+)", text)
    if not (ms and windows):
        raise ValueError(f"anchor {anchor}: no batch duration / window count")
    return float(ms.group(1)) * 1000.0 / float(windows.group(1))


def pl_power_elevation(stat: str) -> float:
    """Apparent active-minus-idle board power (mW) across the nine PL runs.

    The 0.93 ms burst fills under a tenth of one INA219 sample, so this is a
    measurement-floor diagnostic, not switching activity. The paper excludes it.
    """
    elevations = []
    for anchor in ("A", "B", "C"):
        base = ROOT / "results/phase3/energy_runs" / f"anchor_{anchor}"
        for run in sorted(base.glob("run*")):
            text = (run / "energy_batch.txt").read_text(encoding="utf-8")
            idle = float(re.search(r"Static power \(mW\):\s*([\d.]+)", text).group(1))
            active = float(re.search(r"active_mean=([\d.]+)mW", text).group(1))
            elevations.append(active - idle)
    if stat == "mean":
        return mean(elevations)
    if stat == "std":
        return stdev(elevations)
    if stat == "negative":
        return float(sum(e < 0 for e in elevations))
    raise ValueError(stat)


def single_window_latency_us() -> float:
    """Mean single-window DMA latency (us) from the Phase 3 bench."""
    text = read_text("results/phase3/board_bench.txt")
    block = text.split("Single-window DMA latency")[1]
    m = re.search(r"mean\s*=\s*([0-9.]+)\s*us", block)
    if not m:
        raise ValueError("no single-window mean in board_bench.txt")
    return float(m.group(1))


def sustained_stream_latency_us() -> float:
    """Per-window cost of the Phase 2 sequential path (10k sustained run).

    The firmware prints an integer-truncated mean (7 us); recompute from the
    total so the paper can quote 7.5 rather than 7.
    """
    text = read_text("results/phase3/board_batch_bench.txt")
    m = re.search(
        r"Sustained batch \((\d+) windows.*?total\s*=\s*(\d+)\s*us",
        text,
        re.DOTALL,
    )
    if not m:
        raise ValueError("no sustained batch line in board_batch_bench.txt")
    n_windows, total_us = int(m.group(1)), float(m.group(2))
    return total_us / n_windows


def synth_slack(metric: str) -> float:
    """Worst setup/hold slack (ns) from the D=1024 OOC synthesis timing summary."""
    label = {"setup": "Setup", "hold": "Hold"}[metric]
    m = re.search(
        rf"^{label}\s*:\s*(\d+)\s*Failing Endpoints,\s*Worst Slack\s*(-?[0-9.]+)ns",
        read_text("results/dsweep/synth_D1024.txt"),
        re.MULTILINE,
    )
    if not m:
        raise ValueError(f"no {metric} slack line in synth_D1024.txt")
    if int(m.group(1)) != 0:
        return -1.0
    return float(m.group(2))


def slice_occupancy() -> float:
    m = re.search(r"Slices:\s*([\d,]+)\s*/\s*([\d,]+)", read_text("results/phase2/synthesis_utilisation.txt"))
    if not m:
        raise ValueError("no slice count in synthesis_utilisation.txt")
    used, total = (float(g.replace(",", "")) for g in m.groups())
    return used / total * 100


def golden_cases(rel: str, kind: str) -> float:
    """Matched golden vectors, or 0 if the log records any mismatch."""
    m = re.search(rf"PASS: (\d+)/(\d+) {kind} golden cases", read_text(rel))
    if not m:
        raise ValueError(f"no {kind} golden PASS line in {rel}")
    return float(m.group(1)) if m.group(1) == m.group(2) else 0.0


def anchor_row(anchor: str) -> dict:
    for row in load_csv("results/protocol_v2/anchors/summary.csv"):
        if row["anchor"] == anchor:
            return row
    raise ValueError(f"anchor {anchor} missing from summary.csv")


def twist2_36(keep_bits: int) -> dict:
    return load_json(
        f"results/protocol_v2/twist2_36_v2/keep_{keep_bits}/twist2_results.json"
    )["result"]


def ranking_row(method: str) -> dict:
    for row in load_csv("results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv"):
        if row["method"] == method:
            return row
    raise ValueError(f"ranking method {method} missing")


INFORMED_RANKINGS = (
    "fisher",
    "variance",
    "mutual_information",
    "class_mean_separation",
    "prototype_disagreement",
    "entropy",
)


def ranking_subjects() -> list[dict]:
    return load_json(
        "results/protocol_v2/ranking_baselines/ranking_baselines_results.json"
    )["per_subject"]


def ranking_correct_spread() -> float:
    """Largest spread in correct counts across informed rankings, over subjects.

    Zero means every criterion predicts identically on every test window, which
    is the paper's claim in Sec. V-D.
    """
    spreads = []
    for subj in ranking_subjects():
        counts = [subj["methods"][name]["correct"] for name in INFORMED_RANKINGS]
        spreads.append(max(counts) - min(counts))
    return float(max(spreads))


def ranking_jaccard_subject_min() -> float:
    """Lowest per-subject mask overlap with Fisher across the informed criteria."""
    return min(
        subj["methods"][name]["jaccard_vs_fisher"]
        for subj in ranking_subjects()
        for name in INFORMED_RANKINGS
    )


def encoder_step(step: str) -> float:
    for row in load_csv("results/protocol_v2/encoder_ablation/encoder_ablation_summary.csv"):
        if row["step"] == step:
            return float(row["spatial_mean_accuracy"]) * 100
    raise ValueError(f"encoder step {step} missing")


def seed_summary() -> list[dict]:
    return load_json("results/seed_sensitivity/seed_sensitivity_results.json")["meta"]["summary"]


def isodensity_stats() -> dict:
    return load_json(
        "results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json"
    )


def hook_a_flat_span() -> float:
    """Spread in pp across keep ratios at D=1024, CNT_W>=4 — the flat-prune claim."""
    accs = [
        float(r["spatial_mean_accuracy"]) * 100
        for r in load_csv("results/protocol_v2/hook_a/sweep_summary.csv")
        if int(r["D"]) == 1024 and int(r["cnt_w"]) >= 4 and float(r["keep_ratio"]) >= 0.125
    ]
    if not accs:
        raise ValueError("no D=1024 CNT_W>=4 rows in hook A sweep")
    return max(accs) - min(accs)


def active_support_range() -> tuple[float, float]:
    """Active support per item-memory seed, full TEST split (the range the paper quotes)."""
    supports = [s["spatial_mean_active_bit_support"] for s in seed_summary()]
    return min(supports), max(supports)


def active_support_subsampled() -> tuple[float, float]:
    """Same quantity from the active-bit ablation, which subsamples TEST to 15k windows."""
    summary = load_json(
        "results/protocol_v2/active_bits/active_bit_ablation_results.json"
    )["meta"]["summary"]
    pooled = [s["spatial_mean_active_pooled"] for s in summary if s["D"] == 1024]
    return min(pooled), max(pooled)


# --------------------------------------------------------------------------
# Claims — expected values are what the manuscript prints
# --------------------------------------------------------------------------

CLAIMS: list[dict] = [
    # --- Protocol -----------------------------------------------------------
    dict(
        id="split_overlap",
        paper="Table (tab:protocol)",
        claim="Train/test index overlap is 0 on every subject",
        expected=0.0,
        tol=0.0,
        unit="windows",
        evidence="results/protocol_v2/split_audit.json",
        fn=lambda: float(load_json("results/protocol_v2/split_audit.json")["total_overlap"]),
    ),
    dict(
        id="n_test_windows",
        paper="Abstract, Sec. V-A",
        claim="TEST split is 493,512 windows",
        expected=493512,
        tol=0,
        unit="windows",
        evidence="results/protocol_v2/anchors/summary.csv",
        fn=lambda: float(anchor_row("A")["windows"]),
    ),
    # --- Board verification -------------------------------------------------
    dict(
        id="board_pooled_acc",
        paper="Abstract, Table (tab:baselines)",
        claim="Board pooled accuracy 72.78%",
        expected=72.78,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/anchors/anchor_A/board_emg_replay.txt",
        fn=lambda: board_accuracy("results/protocol_v2/anchors/anchor_A/board_emg_replay.txt"),
    ),
    dict(
        id="board_golden_batch",
        paper="Sec. IV-B, Sec. V-A",
        claim="Board matches the golden model on 200/200 batch-DMA vectors",
        expected=200.0,
        tol=0.0,
        unit="vectors",
        evidence="results/phase3/board_bench.txt",
        fn=lambda: golden_cases("results/phase3/board_bench.txt", "batch"),
    ),
    dict(
        id="board_golden_stream",
        paper="Sec. IV-B",
        claim="Board matches the golden model on 200/200 single-window vectors",
        expected=200.0,
        tol=0.0,
        unit="vectors",
        evidence="results/phase3/board_bench.txt",
        fn=lambda: golden_cases("results/phase3/board_bench.txt", "stream"),
    ),
    dict(
        id="board_vs_export_dev",
        paper="Sec. IV-B, Table (tab:protocol)",
        claim="Largest board-vs-export accuracy deviation 0.01 pp (anchor C), gate 0.5 pp",
        expected=0.01,
        tol=0.005,
        unit="pp",
        evidence="results/protocol_v2/anchors/summary.csv",
        fn=lambda: max(
            abs(float(anchor_row(a)["board_pct"]) - float(anchor_row(a)["export_ref_pct"]))
            for a in ("A", "B", "C")
        ),
    ),
    dict(
        id="anchor_c_ref",
        paper="Table (tab:anchors)",
        claim="Anchor C export reference 72.85%",
        expected=72.85,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/anchors/summary.csv",
        fn=lambda: float(anchor_row("C")["export_ref_pct"]),
    ),
    dict(
        id="anchor_c_board",
        paper="Table (tab:anchors), Table (tab:isodensity)",
        claim="Anchor C board accuracy 72.84%",
        expected=72.84,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/anchors/summary.csv",
        fn=lambda: float(anchor_row("C")["board_pct"]),
    ),
    dict(
        id="python_spatial_mean",
        paper="Sec. IV-A, Table (tab:baselines)",
        claim="Python RTL-encoder spatial mean 72.65%",
        expected=72.65,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/emg_baseline.json",
        fn=lambda: load_json("results/protocol_v2/emg_baseline.json")["rtl_encoder_baseline"][
            "python_remeasure"
        ]["spatial_mean"]
        * 100,
    ),
    dict(
        id="arm_spatial_mean",
        paper="Table (tab:baselines)",
        claim="ARM software HDC spatial mean 72.65%",
        expected=72.65,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/arm_baseline/arm_hdc_results.json",
        fn=lambda: load_json("results/protocol_v2/arm_baseline/arm_hdc_results.json")["meta"][
            "spatial_mean_accuracy"
        ]
        * 100,
    ),
    # --- Energy -------------------------------------------------------------
    dict(
        id="pl_energy",
        paper="Table (tab:baselines), Table (tab:anchors)",
        claim="PL DMA batch idle-calibrated energy 11.98 uJ/window",
        expected=11.98,
        tol=0.005,
        unit="uJ/w",
        evidence="results/phase3/energy_summary.txt",
        fn=lambda: energy_total("A"),
    ),
    dict(
        id="arm_energy",
        paper="Table (tab:baselines)",
        claim="ARM software idle-calibrated energy 2088 uJ/window",
        expected=2088.0,
        tol=0.5,
        unit="uJ/w",
        evidence="results/phase3/energy_summary.txt",
        fn=lambda: energy_total("ARM"),
    ),
    dict(
        id="energy_ratio",
        paper="Abstract, Table (tab:baselines) caption",
        claim="ARM/PL idle-calibrated energy ratio ~174x (= latency 176x * idle-power 0.99)",
        expected=174.0,
        tol=1.0,
        unit="x",
        evidence="results/phase3/energy_summary.txt",
        fn=lambda: energy_total("ARM") / energy_total("A"),
    ),
    # --- Latency ------------------------------------------------------------
    dict(
        id="pl_batch_latency",
        paper="Table (tab:phases), Table (tab:baselines)",
        claim="PL DMA batch latency 4.6 us/window (0.927 ms / 200)",
        expected=4.6,
        tol=0.05,
        unit="us/w",
        evidence="results/phase3/energy_runs/anchor_A/run01/energy_batch.txt",
        fn=lambda: batch_latency_us("A"),
    ),
    dict(
        id="arm_batch_latency",
        paper="Table (tab:baselines)",
        claim="ARM software latency 818 us/window (163.6 ms / 200)",
        expected=818.0,
        tol=1.0,
        unit="us/w",
        evidence="results/phase3/energy_runs/anchor_ARM/run01/energy_batch.txt",
        fn=lambda: batch_latency_us("ARM"),
    ),
    dict(
        id="latency_ratio",
        paper="Abstract, Sec. IV-C, Sec. V-A",
        claim="ARM/PL latency ratio ~176x",
        expected=176.0,
        tol=1.0,
        unit="x",
        evidence="results/phase3/energy_runs/anchor_ARM/run01/energy_batch.txt",
        fn=lambda: batch_latency_us("ARM") / batch_latency_us("A"),
    ),
    dict(
        id="pl_elevation_mean",
        paper="Sec. IV-C",
        claim="Apparent PL active elevation averages 50 mW (unresolved)",
        expected=50.0,
        tol=1.0,
        unit="mW",
        evidence="results/phase3/energy_runs/anchor_{A,B,C}/run*/energy_batch.txt",
        fn=lambda: pl_power_elevation("mean"),
    ),
    dict(
        id="pl_elevation_std",
        paper="Sec. IV-C",
        claim="PL elevation std 90 mW, i.e. indistinguishable from zero",
        expected=90.0,
        tol=1.0,
        unit="mW",
        evidence="results/phase3/energy_runs/anchor_{A,B,C}/run*/energy_batch.txt",
        fn=lambda: pl_power_elevation("std"),
    ),
    dict(
        id="pl_elevation_negative",
        paper="Sec. IV-C",
        claim="PL elevation is negative in 3 of 9 runs",
        expected=3.0,
        tol=0.0,
        unit="runs",
        evidence="results/phase3/energy_runs/anchor_{A,B,C}/run*/energy_batch.txt",
        fn=lambda: pl_power_elevation("negative"),
    ),
    dict(
        id="pl_single_window",
        paper="Sec. III",
        claim="Lone window on the SG path costs 58 us (per-call BD ring setup)",
        expected=58.0,
        tol=0.5,
        unit="us/w",
        evidence="results/phase3/board_bench.txt",
        fn=single_window_latency_us,
    ),
    dict(
        id="pl_sustained_stream",
        paper="Table (tab:phases), Sec. III",
        claim="Phase 2 one-xfer-per-window streaming sustains 7.5 us/window",
        expected=7.5,
        tol=0.1,
        unit="us/w",
        evidence="results/phase3/board_batch_bench.txt",
        fn=sustained_stream_latency_us,
    ),
    dict(
        id="pl_throughput",
        paper="Table (tab:prior)",
        claim="PL batch throughput 216k windows/s",
        expected=216000.0,
        tol=1000.0,
        unit="win/s",
        evidence="results/phase3/energy_runs/anchor_A/run01/energy_batch.txt",
        fn=lambda: 1e6 / batch_latency_us("A"),
    ),
    # --- Implementation -----------------------------------------------------
    dict(
        id="slice_occupancy",
        paper="Sec. III",
        claim="Slice occupancy 96.3% (the binding constraint on xc7z020)",
        expected=96.3,
        tol=0.1,
        unit="%",
        evidence="results/phase2/synthesis_utilisation.txt",
        fn=slice_occupancy,
    ),
    dict(
        id="setup_slack",
        paper="Sec. III",
        claim="OOC D=1024 worst setup slack +0.78 ns at 100 MHz, 0 failing endpoints",
        expected=0.78,
        tol=0.01,
        unit="ns",
        evidence="results/dsweep/synth_D1024.txt",
        fn=lambda: synth_slack("setup"),
    ),
    dict(
        id="hold_slack",
        paper="Sec. III",
        claim="OOC D=1024 worst hold slack +0.26 ns, 0 failing endpoints",
        expected=0.26,
        tol=0.01,
        unit="ns",
        evidence="results/dsweep/synth_D1024.txt",
        fn=lambda: synth_slack("hold"),
    ),
    dict(
        id="anchor_energy_spread",
        paper="Sec. V-B",
        claim="Anchor A/B/C energy spread <= 1.5%",
        expected=1.0,
        tol=0.5,
        unit="% spread",
        evidence="results/phase3/energy_summary.txt",
        fn=lambda: (energy_total("A") - energy_total("C")) / energy_total("A") * 100,
    ),
    # --- Iso-density (Python) ----------------------------------------------
    dict(
        id="twist1_gap_mean",
        paper="Abstract, Table (tab:isodensity)",
        claim="Informed - random gap +6.90 pp (30 seeds, subject-level)",
        expected=6.90,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["gap_pp_mean"],
    ),
    dict(
        id="twist1_random_mean",
        paper="Table (tab:isodensity)",
        claim="Random iso-density mean accuracy 65.75%",
        expected=65.75,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["mean_random_accuracy"] * 100,
    ),
    dict(
        id="twist1_ci_low",
        paper="Abstract, Table (tab:isodensity)",
        claim="Subject-bootstrap 95% CI lower bound +4.04 pp",
        expected=4.04,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["bootstrap_mean_95ci_pp"][0],
    ),
    dict(
        id="twist1_ci_high",
        paper="Abstract, Table (tab:isodensity)",
        claim="Subject-bootstrap 95% CI upper bound +9.76 pp",
        expected=9.76,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["bootstrap_mean_95ci_pp"][1],
    ),
    dict(
        id="twist1_gap_min",
        paper="Sec. V-C",
        claim="Smallest per-subject gap +1.79 pp (all five positive)",
        expected=1.79,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["gap_pp_min"],
    ),
    dict(
        id="twist1_gap_max",
        paper="Sec. V-C",
        claim="Largest per-subject gap +11.32 pp",
        expected=11.32,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["gap_pp_max"],
    ),
    dict(
        id="twist1_wilcoxon",
        paper="Sec. V-C",
        claim="Wilcoxon one-sided p = 0.031",
        expected=0.031,
        tol=0.0005,
        unit="p",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["tests"]["wilcoxon_greater_pvalue"],
    ),
    dict(
        id="twist1_ttest",
        paper="Sec. V-C",
        claim="Paired one-sided t-test p = 0.0077",
        expected=0.0077,
        tol=0.00005,
        unit="p",
        evidence="results/protocol_v2/twist1_keep0125_30seed/subject_level_stats.json",
        fn=lambda: isodensity_stats()["summary"]["tests"]["paired_t_greater_pvalue"],
    ),
    # --- Iso-density (silicon) ---------------------------------------------
    dict(
        id="twist1_silicon_informed",
        paper="Table (tab:isodensity)",
        claim="Silicon informed (anchor C) 72.84% pooled",
        expected=72.84,
        tol=0.01,
        unit="%",
        evidence="results/phase3/twist1_silicon/informed_anchor_C/board_emg_replay.txt",
        fn=lambda: board_accuracy(
            "results/phase3/twist1_silicon/informed_anchor_C/board_emg_replay.txt"
        ),
    ),
    dict(
        id="twist1_silicon_random",
        paper="Table (tab:isodensity)",
        claim="Silicon random seed 0 62.51% pooled",
        expected=62.51,
        tol=0.01,
        unit="%",
        evidence="results/phase3/twist1_silicon/random_seed_0/board_emg_replay.txt",
        fn=lambda: board_accuracy(
            "results/phase3/twist1_silicon/random_seed_0/board_emg_replay.txt"
        ),
    ),
    dict(
        id="twist1_silicon_gap",
        paper="Abstract, Table (tab:isodensity)",
        claim="Silicon iso-density gap +10.33 pp (seed 0)",
        expected=10.33,
        tol=0.01,
        unit="pp",
        evidence="results/phase3/twist1_silicon/",
        fn=lambda: board_accuracy(
            "results/phase3/twist1_silicon/informed_anchor_C/board_emg_replay.txt"
        )
        - board_accuracy("results/phase3/twist1_silicon/random_seed_0/board_emg_replay.txt"),
    ),
    # --- Ranking baselines --------------------------------------------------
    dict(
        id="ranking_fisher",
        paper="Sec. V-D",
        claim="Fisher at 128 bits 72.58% spatial mean",
        expected=72.58,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv",
        fn=lambda: float(ranking_row("fisher")["spatial_mean_accuracy"]) * 100,
    ),
    dict(
        id="ranking_informed_tie",
        paper="Sec. V-D",
        claim="All informed criteria tie Fisher (max |gap| = 0 pp)",
        expected=0.0,
        tol=0.001,
        unit="pp",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv",
        fn=lambda: max(
            abs(float(ranking_row(m)["spatial_mean_gap_pp_vs_fisher"]))
            for m in (
                "variance",
                "mutual_information",
                "class_mean_separation",
                "prototype_disagreement",
                "entropy",
            )
        ),
    ),
    dict(
        id="ranking_identical_preds",
        paper="Sec. V-D",
        claim="All six informed rankings predict identically on every test window",
        expected=0.0,
        tol=0.0,
        unit="windows",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_results.json",
        fn=ranking_correct_spread,
    ),
    dict(
        id="ranking_jaccard_subject_min",
        paper="Sec. V-D",
        claim="Lowest per-subject mask overlap with Fisher 0.11",
        expected=0.113,
        tol=0.005,
        unit="J",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_results.json",
        fn=ranking_jaccard_subject_min,
    ),
    dict(
        id="ranking_jaccard_min",
        paper="Sec. V-D",
        claim="Lowest informed-mask mean Jaccard vs Fisher 0.18",
        expected=0.18,
        tol=0.005,
        unit="J",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv",
        fn=lambda: min(
            float(ranking_row(m)["spatial_mean_jaccard_vs_fisher"])
            for m in (
                "variance",
                "mutual_information",
                "class_mean_separation",
                "prototype_disagreement",
                "entropy",
            )
        ),
    ),
    dict(
        id="ranking_jaccard_max",
        paper="Sec. V-D",
        claim="Highest informed-mask mean Jaccard vs Fisher 0.95",
        expected=0.95,
        tol=0.005,
        unit="J",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv",
        fn=lambda: max(
            float(ranking_row(m)["spatial_mean_jaccard_vs_fisher"])
            for m in (
                "variance",
                "mutual_information",
                "class_mean_separation",
                "prototype_disagreement",
                "entropy",
            )
        ),
    ),
    dict(
        id="ranking_random_full",
        paper="Sec. V-D",
        claim="Uniform random over 1024 bits 64.55% (-8.04 pp)",
        expected=64.55,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv",
        fn=lambda: float(ranking_row("random_full")["spatial_mean_accuracy"]) * 100,
    ),
    dict(
        id="ranking_random_active",
        paper="Sec. V-D",
        claim="Fair random from active support 71.45% (-1.13 pp)",
        expected=71.45,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/ranking_baselines/ranking_baselines_summary.csv",
        fn=lambda: float(ranking_row("random_active")["spatial_mean_accuracy"]) * 100,
    ),
    # --- Seed sensitivity ---------------------------------------------------
    dict(
        id="seed_acc_min",
        paper="Sec. V-E",
        claim="Full-width accuracy floor across item-memory seeds 72.2%",
        expected=72.2,
        tol=0.1,
        unit="%",
        evidence="results/seed_sensitivity/seed_sensitivity_results.json",
        fn=lambda: min(s["spatial_mean_full_width_accuracy"] for s in seed_summary()) * 100,
    ),
    dict(
        id="seed_acc_max",
        paper="Sec. V-E",
        claim="Full-width accuracy ceiling across item-memory seeds 73.4%",
        expected=73.4,
        tol=0.1,
        unit="%",
        evidence="results/seed_sensitivity/seed_sensitivity_results.json",
        fn=lambda: max(s["spatial_mean_full_width_accuracy"] for s in seed_summary()) * 100,
    ),
    dict(
        id="seed_gap_min",
        paper="Sec. V-E",
        claim="Smallest per-seed iso-density gap +5.55 pp (above the 5 pp target)",
        expected=5.55,
        tol=0.01,
        unit="pp",
        evidence="results/seed_sensitivity/seed_sensitivity_results.json",
        fn=lambda: min(s["spatial_mean_gap_pp_at_gap"] for s in seed_summary()),
    ),
    dict(
        id="seed_gap_max",
        paper="Sec. V-E",
        claim="Largest per-seed iso-density gap +8.79 pp",
        expected=8.79,
        tol=0.01,
        unit="pp",
        evidence="results/seed_sensitivity/seed_sensitivity_results.json",
        fn=lambda: max(s["spatial_mean_gap_pp_at_gap"] for s in seed_summary()),
    ),
    # --- Cross-subject ------------------------------------------------------
    dict(
        id="twist2_local",
        paper="Table (tab:twist2)",
        claim="Pilot local oracle / unpruned 67.66%",
        expected=67.66,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/twist2_keep0125/twist2_results.json",
        fn=lambda: load_json("results/protocol_v2/twist2_keep0125/twist2_results.json")["result"][
            "mean_local_oracle_accuracy"
        ]
        * 100,
    ),
    dict(
        id="twist2_pooled",
        paper="Table (tab:twist2)",
        claim="Pilot pooled transfer 66.64%",
        expected=66.64,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/twist2_keep0125/twist2_results.json",
        fn=lambda: load_json("results/protocol_v2/twist2_keep0125/twist2_results.json")["result"][
            "mean_pooled_transfer_accuracy"
        ]
        * 100,
    ),
    dict(
        id="twist2_gap",
        paper="Abstract, Table (tab:twist2)",
        claim="Pilot local - pooled gap +1.02 pp (within the 3 pp bound)",
        expected=1.02,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist2_keep0125/twist2_results.json",
        fn=lambda: load_json("results/protocol_v2/twist2_keep0125/twist2_results.json")["result"][
            "mean_gap_local_minus_pooled_pp"
        ],
    ),
    dict(
        id="twist2_36_keep32_local",
        paper="Table (tab:twist2_36)",
        claim="36-subject keep=32 local oracle 60.91%",
        expected=60.91,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/twist2_36_v2/keep_32/twist2_results.json",
        fn=lambda: twist2_36(32)["mean_local_oracle_accuracy"] * 100,
    ),
    dict(
        id="twist2_36_keep32_pooled",
        paper="Table (tab:twist2_36)",
        claim="36-subject keep=32 pooled transfer 63.50%",
        expected=63.50,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/twist2_36_v2/keep_32/twist2_results.json",
        fn=lambda: twist2_36(32)["mean_pooled_transfer_accuracy"] * 100,
    ),
    dict(
        id="twist2_36_keep32_gap",
        paper="Abstract, Table (tab:twist2_36)",
        claim="36-subject keep=32 gap -2.59 pp (worst case, within bound)",
        expected=-2.59,
        tol=0.01,
        unit="pp",
        evidence="results/protocol_v2/twist2_36_v2/keep_32/twist2_results.json",
        fn=lambda: twist2_36(32)["mean_gap_local_minus_pooled_pp"],
    ),
    dict(
        id="twist2_36_lossless_gap",
        paper="Abstract, Table (tab:twist2_36)",
        claim="Gap is exactly 0.00 pp for keep >= 64 bits",
        expected=0.0,
        tol=0.0,
        unit="pp",
        evidence="results/protocol_v2/twist2_36_v2/keep_*/twist2_results.json",
        fn=lambda: max(
            abs(twist2_36(k)["mean_gap_local_minus_pooled_pp"]) for k in (64, 96, 128, 192, 256)
        ),
    ),
    dict(
        id="twist2_36_unpruned",
        paper="Table (tab:twist2_36)",
        claim="36-subject unpruned baseline 59.87%",
        expected=59.87,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/twist2_36_v2/keep_64/twist2_results.json",
        fn=lambda: twist2_36(64)["mean_unpruned_accuracy"] * 100,
    ),
    # --- Encoder ablation ---------------------------------------------------
    dict(
        id="encoder_stage_b_lit",
        paper="Table (tab:encoder)",
        claim="Stage B BSC, literature protocol 90.17%",
        expected=90.17,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/encoder_ablation/encoder_ablation_summary.csv",
        fn=lambda: encoder_step("stage_b_literature_fulltest"),
    ),
    dict(
        id="encoder_stage_b_hdc2",
        paper="Table (tab:encoder)",
        claim="Stage B under HDC-2 89.37%",
        expected=89.37,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/encoder_ablation/encoder_ablation_summary.csv",
        fn=lambda: encoder_step("stage_b_hdc2"),
    ),
    dict(
        id="encoder_rtl_4bind",
        paper="Table (tab:encoder)",
        claim="RTL item memory + 4 binds 73.28%",
        expected=73.28,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/encoder_ablation/encoder_ablation_summary.csv",
        fn=lambda: encoder_step("rtl_4bind"),
    ),
    dict(
        id="encoder_rtl_deployed",
        paper="Table (tab:encoder)",
        claim="Deployed RTL encoder (20 binds) 72.89%",
        expected=72.89,
        tol=0.01,
        unit="%",
        evidence="results/protocol_v2/encoder_ablation/encoder_ablation_summary.csv",
        fn=lambda: encoder_step("rtl_20bind"),
    ),
    # --- Design space and active support ------------------------------------
    dict(
        id="hook_a_flat",
        paper="Sec. V-B",
        claim="Accuracy flat at D=1024, CNT_W>=4 from 0% to 87.5% prune",
        expected=0.0,
        tol=0.001,
        unit="pp spread",
        evidence="results/protocol_v2/hook_a/sweep_summary.csv",
        fn=hook_a_flat_span,
    ),
    dict(
        id="active_support_min",
        paper="Sec. IV-D, Sec. VI",
        claim="Active support floor ~203 of 1024 positions (seeds 1/7/21/42, full TEST)",
        expected=203.0,
        tol=0.5,
        unit="bits",
        evidence="results/seed_sensitivity/seed_sensitivity_results.json",
        fn=lambda: active_support_range()[0],
    ),
    dict(
        id="active_support_max",
        paper="Sec. IV-D, Sec. VI",
        claim="Active support ceiling ~210 of 1024 positions (seeds 1/7/21/42, full TEST)",
        expected=210.0,
        tol=0.5,
        unit="bits",
        evidence="results/seed_sensitivity/seed_sensitivity_results.json",
        fn=lambda: active_support_range()[1],
    ),
    dict(
        id="active_support_ranking_run",
        paper="Sec. V-D",
        claim="Active support ~209 bits in the ranking-baseline run (seed 42, 15k TEST windows)",
        expected=209.0,
        tol=0.5,
        unit="bits",
        evidence="results/protocol_v2/active_bits/active_bit_ablation_results.json",
        fn=lambda: active_support_subsampled()[1],
    ),
]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def run_claims(only: str | None = None) -> list[dict]:
    results = []
    for claim in CLAIMS:
        if only and only not in claim["id"]:
            continue
        row = {k: claim[k] for k in ("id", "paper", "claim", "expected", "tol", "unit", "evidence")}
        try:
            actual = float(claim["fn"]())
            row["actual"] = actual
            row["status"] = "PASS" if abs(actual - claim["expected"]) <= claim["tol"] else "FAIL"
        except FileNotFoundError as exc:
            row["actual"] = None
            row["status"] = "MISSING"
            row["error"] = f"missing artifact: {exc}"
        except Exception as exc:  # noqa: BLE001 - report any parse failure as a check failure
            row["actual"] = None
            row["status"] = "ERROR"
            row["error"] = f"{type(exc).__name__}: {exc}"
        results.append(row)
    return results


def fmt(value: float | None) -> str:
    if value is None:
        return "--"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) < 0.01 and value != 0:
        return f"{value:.5f}"
    return f"{value:.2f}"


def print_table(results: list[dict]) -> None:
    width = max(len(r["id"]) for r in results)
    print(f"{'CLAIM'.ljust(width)}  {'PAPER':<26} {'EXPECTED':>10} {'ACTUAL':>10}  STATUS")
    print("-" * (width + 60))
    for r in results:
        print(
            f"{r['id'].ljust(width)}  {r['paper'][:26]:<26} "
            f"{fmt(r['expected']):>10} {fmt(r['actual']):>10}  {r['status']}"
        )
        if r["status"] not in ("PASS",):
            detail = r.get("error", r["claim"])
            print(f"{' ' * (width + 2)}  -> {detail}")


def print_markdown(results: list[dict]) -> None:
    print("| Claim | Paper | Expected | Artifact | Status |")
    print("|-------|-------|----------|----------|--------|")
    for r in results:
        mark = {"PASS": "PASS", "FAIL": "**FAIL**"}.get(r["status"], r["status"])
        print(
            f"| {r['claim']} | {r['paper']} | {fmt(r['expected'])} {r['unit']} | "
            f"`{r['evidence']}` | {mark} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="PATH", help="write machine-readable results here")
    parser.add_argument("--markdown", action="store_true", help="emit a markdown evidence table")
    parser.add_argument("--only", metavar="SUBSTR", help="run only claims whose id contains SUBSTR")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="treat absent artifacts as skipped instead of failures (fresh clone, board logs absent)",
    )
    args = parser.parse_args()

    results = run_claims(args.only)
    if not results:
        print("no claims matched", file=sys.stderr)
        return 2

    if args.markdown:
        print_markdown(results)
    else:
        print_table(results)

    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "MISSING", "ERROR")}
    bad = counts["FAIL"] + counts["ERROR"] + (0 if args.allow_missing else counts["MISSING"])

    if not args.markdown:
        print()
        print(
            f"{counts['PASS']}/{len(results)} claims verified"
            + (f" · {counts['FAIL']} failed" if counts["FAIL"] else "")
            + (f" · {counts['MISSING']} missing" if counts["MISSING"] else "")
            + (f" · {counts['ERROR']} errored" if counts["ERROR"] else "")
        )

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": counts, "claims": results}, indent=2), encoding="utf-8"
        )
        if not args.markdown:
            print(f"wrote {out}")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
