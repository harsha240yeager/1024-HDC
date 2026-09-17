#!/usr/bin/env python3
"""Merge board_emg_replay.txt into seed_summary.json without re-running full prediction."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "protocol_v2" / "twist1_silicon"
INFORMED_BOARD = 72.84


def parse_board_acc(path: Path, n_windows: int) -> float | None:
    if not path.is_file():
        return None
    text = path.read_text()
    m = re.search(
        r"EMG replay: N=(\d+) correct=(\d+) accuracy=([\d.]+)%",
        text,
    )
    if not m:
        return None
    n, correct, acc = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if n != n_windows or correct <= 0:
        return None
    return acc


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    rows = []
    for seed in range(10):
        sdir = out_dir / f"random_seed_{seed}"
        pred_path = sdir / "prediction.json"
        if not pred_path.is_file():
            continue
        row = json.loads(pred_path.read_text())
        board = parse_board_acc(
            sdir / "board_emg_replay.txt",
            int(row["n_windows"]),
        )
        if board is not None:
            row["board_accuracy_pct"] = board
            row["board_vs_export_delta_pp"] = round(
                board - row["export_ref_accuracy_pct"], 4
            )
            row["board_measured"] = True
            row["gap_vs_informed_board_pp"] = round(INFORMED_BOARD - board, 4)
        else:
            row["board_measured"] = False
        rows.append(row)
        pred_path.write_text(json.dumps(row, indent=2) + "\n")

    if not rows:
        print("no prediction.json files found", file=sys.stderr)
        return 1

    summary_path = out_dir / "seed_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text())
    else:
        summary = {}

    summary.update(
        {
            "issue": 26,
            "keep_ratio": 0.125,
            "informed_anchor_C_board_pct": INFORMED_BOARD,
            "informed_anchor_C_export_ref_pct": 72.85,
            "n_windows": rows[0]["n_windows"],
            "prediction_method": "export_ref_calibrated",
            "calibration": {
                "seed_0_board_pct": 62.51,
                "seed_0_export_ref_pct": 62.51,
                "board_export_delta_pp": 0.0,
            },
            "seeds": rows,
        }
    )

    predicted = [r["predicted_board_accuracy_pct"] for r in rows]
    gaps = [r["gap_vs_informed_board_pp"] for r in rows]
    summary["aggregate_predicted"] = {
        "mean_accuracy_pct": round(float(np.mean(predicted)), 4),
        "std_accuracy_pct": round(float(np.std(predicted, ddof=1)) if len(predicted) > 1 else 0.0, 4),
        "mean_gap_pp": round(float(np.mean(gaps)), 4),
        "std_gap_pp": round(float(np.std(gaps, ddof=1)) if len(gaps) > 1 else 0.0, 4),
        "min_gap_pp": round(float(min(gaps)), 4),
        "max_gap_pp": round(float(max(gaps)), 4),
    }
    measured = [r for r in rows if r.get("board_measured")]
    if measured:
        bg = [r["gap_vs_informed_board_pp"] for r in measured]
        summary["aggregate_measured"] = {
            "n_seeds": len(measured),
            "mean_gap_pp": round(float(np.mean(bg)), 4),
            "std_gap_pp": round(float(np.std(bg, ddof=1)) if len(bg) > 1 else 0.0, 4),
        }

    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"Wrote {summary_path} — measured {len(measured)}/{len(rows)} seeds",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
