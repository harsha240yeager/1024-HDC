#!/usr/bin/env python3
"""Build committed CSV for issue #32 from #31 board_eval_summary + synth util."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "results" / "protocol_v2" / "narrow_rtl" / "board_eval_summary.json"
OUT = REPO / "results" / "figures" / "narrow_vs_baseline_pareto.csv"
UTIL = REPO / "results" / "dsweep" / "narrow_vs_baseline_util.csv"


def parse_energy_mean(text: str | None) -> float | None:
    if not text:
        return None
    m = re.match(r"([0-9.]+)", text.strip())
    return float(m.group(1)) if m else None


def main() -> int:
    ev = json.loads(EVAL.read_text())
    acc_c = ev["accuracy_emg_493512"]["C"]["baseline_pl"]["accuracy_pct"]
    energy_block = ev.get("energy_uj_per_window_anchor_c") or {}
    base_e = parse_energy_mean(
        (energy_block.get("baseline_pl") or {}).get("total_uj_per_window")
    )
    narrow_e = parse_energy_mean(
        (energy_block.get("narrow_pl") or {}).get("total_uj_per_window")
    )
    if narrow_e is None:
        narrow_e = base_e

    rows = [
        {
            "variant": "baseline",
            "scope": "integrated_placed",
            "keep_ratio": 0.125,
            "k_bits": 1024,
            "lut": ev["lut_integrated"]["baseline"],
            "batch_us_per_window": ev["latency_batch_200_windows_us"]["baseline"],
            "energy_uj_per_window": base_e,
            "accuracy_pct_anchor_c": acc_c,
            "source": "board_eval_summary.json + integrated util",
        },
        {
            "variant": "narrow",
            "scope": "integrated_placed",
            "keep_ratio": 0.125,
            "k_bits": 128,
            "lut": ev["lut_integrated"]["narrow"],
            "batch_us_per_window": ev["latency_batch_200_windows_us"]["narrow"],
            "energy_uj_per_window": narrow_e,
            "accuracy_pct_anchor_c": ev["accuracy_emg_493512"]["C"]["narrow_pl"][
                "accuracy_pct"
            ],
            "source": "board_eval_summary.json (#31)",
        },
    ]

    if UTIL.is_file():
        with UTIL.open(newline="") as f:
            for r in csv.DictReader(f):
                if r["scope"] != "ooc_integrated":
                    continue
                rows.append(
                    {
                        "variant": r["variant"],
                        "scope": "ooc_bd_wrapper",
                        "keep_ratio": 0.125,
                        "k_bits": int(r["k_bits"]),
                        "lut": int(r["lut"]),
                        "batch_us_per_window": "",
                        "energy_uj_per_window": "",
                        "accuracy_pct_anchor_c": "",
                        "source": r["report"],
                    }
                )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {OUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
