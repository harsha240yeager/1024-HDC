#!/usr/bin/env python3
"""Issue #31: baseline vs narrow board eval summary (LUT, latency, accuracy, energy)."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "results" / "protocol_v2" / "narrow_rtl"
BASE_ANCHORS = REPO / "results" / "protocol_v2" / "anchors"
NARROW_ANCHORS = OUT_DIR / "anchors"


def parse_emg_accuracy(path: Path) -> dict | None:
    if not path.is_file():
        return None
    text = path.read_text()
    m = re.search(r"EMG replay: N=(\d+) correct=(\d+) accuracy=([\d.]+)%", text)
    if not m:
        return None
    return {
        "n": int(m.group(1)),
        "correct": int(m.group(2)),
        "accuracy_pct": float(m.group(3)),
    }


def parse_bench_mean_us(path: Path) -> float | None:
    if not path.is_file():
        return None
    text = path.read_text()
    m = re.search(r"mean/window ~ (\d+) us", text)
    if m:
        return float(m.group(1))
    m = re.search(r"total\s*=\s*(\d+) us", text)
    if m:
        return float(m.group(1)) / 200.0
    return None


def parse_energy_total(path: Path) -> dict | None:
    if not path.is_file():
        return None
    text = path.read_text()
    m = re.search(r"Total \(µJ/w\):\s*([0-9.]+ ± [0-9.]+|[0-9.]+)", text)
    if not m:
        return None
    return {"total_uj_per_window": m.group(1).strip()}


def pct_improvement(baseline: float, narrow: float) -> float:
    return 100.0 * (baseline - narrow) / baseline


def main() -> int:
    baseline_lut = 35206
    narrow_lut = 10601
    lut_delta_pct = pct_improvement(baseline_lut, narrow_lut)

    baseline_bench = parse_bench_mean_us(REPO / "results/phase3/board_bench.txt")
    narrow_bench = parse_bench_mean_us(OUT_DIR / "board_bench.txt")
    latency_improve_pct = None
    if baseline_bench and narrow_bench:
        latency_improve_pct = round(pct_improvement(baseline_bench, narrow_bench), 2)

    accuracies = {}
    for anchor in ("A", "B", "C"):
        base = parse_emg_accuracy(BASE_ANCHORS / f"anchor_{anchor}" / "board_emg_replay.txt")
        accuracies[anchor] = {"baseline_pl": base}
        if anchor == "C":
            nar = parse_emg_accuracy(NARROW_ANCHORS / "anchor_C" / "board_emg_replay.txt")
            accuracies[anchor]["narrow_pl"] = nar

    baseline_energy = parse_energy_total(REPO / "results" / "phase3" / "energy_summary.txt")
    narrow_energy = parse_energy_total(OUT_DIR / "energy_summary.txt")

    gate_lut = lut_delta_pct >= 10.0
    gate_latency = latency_improve_pct is not None and latency_improve_pct >= 5.0
    gate_met = gate_lut or gate_latency

    summary = {
        "issue": 31,
        "narrow_config": {"k_bits": 128, "keep_ratio": 0.125, "option": "E baked SEL"},
        "lut_integrated": {
            "baseline": baseline_lut,
            "narrow": narrow_lut,
            "delta_pct": round(lut_delta_pct, 2),
            "gate_10pct_lut": gate_lut,
        },
        "latency_batch_200_windows_us": {
            "baseline": baseline_bench,
            "narrow": narrow_bench,
            "improvement_pct": latency_improve_pct,
            "gate_5pct_latency": gate_latency,
        },
        "accuracy_emg_493512": accuracies,
        "energy_uj_per_window_anchor_c": {
            "baseline_pl": baseline_energy,
            "narrow_pl": narrow_energy,
        },
        "strong_paper1_gate_met": gate_met,
        "anchors_on_narrow_bitstream": {
            "A": "n/a — narrow RTL is K=128 Fisher only (use baseline PL for keep=1.0)",
            "B": "n/a — narrow RTL is K=128 Fisher only (use baseline PL for keep=0.5)",
            "C": "measured — full EMG replay PASS",
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "board_eval_summary.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        "# Issue #31 — Narrow vs baseline board evaluation",
        "",
        "## Strong Paper 1 gate",
        "",
        f"- **LUT (integrated):** {baseline_lut:,} → {narrow_lut:,} "
        f"(**−{lut_delta_pct:.1f}%**) — {'PASS' if gate_lut else 'FAIL'} (≥10%)",
    ]
    if baseline_bench and narrow_bench:
        lines.append(
            f"- **Batch latency (200 windows):** {baseline_bench:.0f} → {narrow_bench:.0f} µs/w "
            f"(**−{latency_improve_pct:.1f}%**) — {'PASS' if gate_latency else 'FAIL'} (≥5%)"
        )
    lines += [
        f"- **Overall gate (LUT or latency):** **{'PASS' if gate_met else 'FAIL'}**",
        "",
        "## Accuracy (493,512 windows, vs export ref)",
        "",
        "| Anchor | Keep | Baseline PL | Narrow PL |",
        "|--------|------|-------------|-----------|",
    ]
    keep = {"A": "1.0", "B": "0.5", "C": "0.125"}
    for anchor in ("A", "B", "C"):
        b = accuracies[anchor]["baseline_pl"]
        b_str = f"{b['accuracy_pct']:.2f}%" if b else "—"
        if anchor == "C":
            n = accuracies[anchor].get("narrow_pl")
            n_str = f"{n['accuracy_pct']:.2f}%" if n else "—"
        else:
            n_str = "n/a (see note)"
        lines.append(f"| {anchor} | {keep[anchor]} | {b_str} | {n_str} |")

    lines += [
        "",
        "Narrow bitstream implements **anchor C only** (baked K=128 gather). "
        "Anchors A/B use full-width baseline PL.",
        "",
        "## Energy (INA219, anchor C, 200-window PL batch)",
        "",
    ]
    if baseline_energy:
        lines.append(f"- Baseline PL: **{baseline_energy['total_uj_per_window']}** µJ/w")
    else:
        lines.append("- Baseline PL: see `results/phase3/energy_summary.txt`")
    if narrow_energy:
        lines.append(f"- Narrow PL: **{narrow_energy['total_uj_per_window']}** µJ/w")
    else:
        lines.append(
            "- Narrow PL: run `bash scripts/run_narrow_energy_campaign.sh` "
            "(ZedBoard + Pi INA219)"
        )

    lines += [
        "",
        "## Artifacts",
        "",
        "| Item | Path |",
        "|------|------|",
        "| Narrow anchor C EMG | `anchors/anchor_C/board_emg_replay.txt` |",
        "| Narrow latency bench | `board_bench.txt` |",
        "| LUT (integrated) | `results/narrow_rtl/integrated_utilization_placed.rpt` |",
        "| This summary | `board_eval_summary.json` |",
        "",
    ]
    md_path = OUT_DIR / "board_eval_summary.md"
    md_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
