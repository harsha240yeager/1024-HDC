#!/usr/bin/env python3
"""
M16/M17 - one-command EMG baseline runner (frozen).

Reads the frozen config (config/emg_baseline.json), runs the project BSC
baseline at the frozen D across the configured seeds to get mean +/- std, and
(optionally) the MAP/D=10000 literal-parity anchor once. Writes a commit-ready
snapshot to results/emg_baseline.json and prints the frozen one-liner:

    May EMG baseline = X% +/- s  under protocol P

Usage:
    python run_emg_baseline.py [--config config/emg_baseline.json]
                               [--no-parity] [--quick]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "repro"))

import stage_a_icrc          # noqa: E402
import stage_b_bsc           # noqa: E402


def mean_std(xs):
    a = np.asarray(xs, dtype=float)
    return float(a.mean()), float(a.std(ddof=0))


def run(config_path: Path, run_parity: bool, quick: bool):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    subjects = cfg["dataset"]["subjects"]
    D = cfg["project_baseline_model"]["D"]
    seeds = [cfg["seed"]] if quick else cfg["seeds_for_std"]

    print(f"== Project baseline: BSC D={D}, subjects={subjects}, seeds={seeds} ==")
    sp_means, st_means = [], []
    per_seed = {}
    for sd in seeds:
        res = stage_b_bsc.run([D], subjects, "both", sd)
        sp = res["spatial"][D]["mean"]
        st = res["spatiotemporal"][D]["mean"]
        sp_means.append(sp)
        st_means.append(st)
        per_seed[sd] = {"spatial": sp, "spatiotemporal": st}

    sp_m, sp_s = mean_std(sp_means)
    st_m, st_s = mean_std(st_means)

    snapshot = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "config_file": str(config_path.relative_to(HERE)) if config_path.is_relative_to(HERE) else str(config_path),
        "protocol_id": cfg["protocol"]["id"],
        "subjects": subjects,
        "project_baseline": {
            "model": cfg["project_baseline_model"]["name"],
            "D": D,
            "seeds": seeds,
            "spatial":        {"mean": sp_m, "std": sp_s},
            "spatiotemporal": {"mean": st_m, "std": st_s},
            "per_seed": per_seed,
        },
    }

    if run_parity and cfg.get("run_parity_anchor", False):
        Dp = cfg["parity_anchor_model"]["D"]
        print(f"\n== Parity anchor: MAP D={Dp}, seed={cfg['seed']} ==")
        ra = stage_a_icrc.run(Dp, subjects, "both", cfg["seed"])
        snapshot["parity_anchor"] = {
            "model": cfg["parity_anchor_model"]["name"],
            "D": Dp,
            "seed": cfg["seed"],
            "spatial":        {"mean": ra["spatial"]["mean"]},
            "spatiotemporal": {"mean": ra["spatiotemporal"]["mean"]},
            "paper": {"spatial": 0.908, "spatiotemporal": 0.978},
        }

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "emg_baseline.json"
    out.write_text(json.dumps(snapshot, indent=2))

    pid = cfg["protocol"]["id"]
    print("\n" + "=" * 70)
    print("FROZEN MAY 2026 EMG BASELINE")
    print("=" * 70)
    print(f"  Project (BSC, D={D}) spatial        = {sp_m*100:5.2f}% +/- {sp_s*100:.2f}")
    print(f"  Project (BSC, D={D}) spatiotemporal = {st_m*100:5.2f}% +/- {st_s*100:.2f}")
    if "parity_anchor" in snapshot:
        pa = snapshot["parity_anchor"]
        print(f"  Anchor  (MAP, D={pa['D']}) spatial     = {pa['spatial']['mean']*100:5.2f}%  (paper 90.8%)")
        print(f"  Anchor  (MAP, D={pa['D']}) spatiotemp. = {pa['spatiotemporal']['mean']*100:5.2f}%  (paper 97.8%)")
    print(f"\n  >>> May EMG baseline = {sp_m*100:.2f}% +/- {sp_s*100:.2f} (spatial) "
          f"under protocol {pid}")
    print(f"  snapshot -> {out}")
    return snapshot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=HERE / "config" / "emg_baseline.json")
    ap.add_argument("--no-parity", action="store_true", help="skip the slow MAP parity anchor")
    ap.add_argument("--quick", action="store_true", help="single seed only (no std)")
    args = ap.parse_args()

    t0 = time.time()
    run(args.config, run_parity=not args.no_parity, quick=args.quick)
    print(f"  total {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
