#!/usr/bin/env python3
"""
M16/M17 - one-command EMG baseline runner (frozen).

Reads config/emg_baseline.json and reports:

  1. Stage B spatial reference (~90.30%) — Python comparison to Rahimi / literature
  2. RTL encoder baseline (~74.24%) — cached from board PASS + optional re-measure
  3. (optional) MAP parity anchor — literal Rahimi 2016 numbers

Writes python_ref/results/emg_baseline.json.

Usage:
    python run_emg_baseline.py
    python run_emg_baseline.py --quick --no-parity
    python run_emg_baseline.py --measure-rtl-ref --rtl-max-windows 5000
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
REPO = HERE.parent
sys.path.insert(0, str(HERE / "repro"))
sys.path.insert(0, str(REPO))

import stage_a_icrc  # noqa: E402
import stage_b_bsc  # noqa: E402


def mean_std(xs):
    a = np.asarray(xs, dtype=float)
    return float(a.mean()), float(a.std(ddof=0))


def measure_rtl_encoder_spatial(
    cfg: dict,
    item_mem_seed: int,
    max_windows: int | None,
) -> dict:
    """Recompute hdc_ref spatial mean (slow on full TEST split)."""
    from hdc_ref import HDCConfig  # noqa: E402
    from scripts.export_emg_board_vectors import evaluate_subject_hdc_ref  # noqa: E402

    subjects = cfg["dataset"]["subjects"]
    seed = int(cfg["seed"])
    train_frac = float(cfg["protocol"]["train_fraction"])
    D = int(cfg["rtl_encoder_baseline"]["D"])
    hdc_cfg = HDCConfig(D=D, seed=item_mem_seed)

    accs = []
    per_subject = {}
    for s in subjects:
        r = evaluate_subject_hdc_ref(
            s, hdc_cfg, seed, train_frac, item_mem_seed, max_windows
        )
        accs.append(r["accuracy"])
        per_subject[str(s)] = float(r["accuracy"])
    mean_acc = float(np.mean(accs)) if accs else 0.0
    return {
        "spatial_mean": mean_acc,
        "per_subject": per_subject,
        "max_windows_per_subject": max_windows,
        "item_mem_seed": item_mem_seed,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "source": "python_recompute",
    }


def run(
    config_path: Path,
    run_parity: bool,
    quick: bool,
    measure_rtl: bool,
    rtl_max_windows: int | None,
):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    subjects = cfg["dataset"]["subjects"]
    D = cfg["project_baseline_model"]["D"]
    seeds = [cfg["seed"]] if quick else cfg["seeds_for_std"]

    print("=" * 70)
    print("EMG BASELINES (dual-track — see docs/Baseline_vs_RTL_Encoder.md)")
    print("=" * 70)

    print(f"\n== (1) Stage B spatial reference: BSC D={D}, subjects={subjects} ==")
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

    rtl_cfg = cfg.get("rtl_encoder_baseline", {})
    rtl_cached = float(rtl_cfg.get("spatial_mean", 0.0))
    rtl_seed = int(rtl_cfg.get("item_mem_seed", 42))

    print(f"\n== (2) RTL encoder baseline (hdc_ref / encoder_top.sv, seed={rtl_seed}) ==")
    print(
        f"  Cached (board PASS): {rtl_cached * 100:.2f}%  "
        f"({rtl_cfg.get('n_correct', '?')}/{rtl_cfg.get('n_test_windows', '?')} windows)"
    )
    print(f"  Evidence: {rtl_cfg.get('evidence', 'results/phase3/board_emg_replay.txt')}")
    print("  Board PASS: |board_acc - export_ref| <= 0.5%  (NOT vs Stage B 90%)")

    rtl_measured = None
    if measure_rtl:
        cap = rtl_max_windows
        if cap is None and quick:
            cap = 5000
        print(f"\n  Re-measuring hdc_ref spatial (max_windows/subject={cap}) ...")
        t0 = time.time()
        rtl_measured = measure_rtl_encoder_spatial(cfg, rtl_seed, cap)
        print(f"  Recomputed mean: {rtl_measured['spatial_mean'] * 100:.2f}%  ({time.time()-t0:.0f}s)")

    snapshot = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "config_file": (
            str(config_path.relative_to(HERE))
            if config_path.is_relative_to(HERE)
            else str(config_path)
        ),
        "protocol_id": cfg["protocol"]["id"],
        "subjects": subjects,
        "stage_b_reference": {
            "model": cfg["project_baseline_model"]["name"],
            "D": D,
            "seeds": seeds,
            "spatial": {"mean": sp_m, "std": sp_s},
            "spatiotemporal": {"mean": st_m, "std": st_s},
            "per_seed": per_seed,
            "role": "Python reference vs Rahimi / literature (~90%)",
        },
        "rtl_encoder_baseline": {
            **rtl_cfg,
            "role": "Deployed encoder; board verification path (~74%)",
            "python_remeasure": rtl_measured,
        },
    }

    if run_parity and cfg.get("run_parity_anchor", False):
        Dp = cfg["parity_anchor_model"]["D"]
        print(f"\n== (3) MAP parity anchor: D={Dp}, seed={cfg['seed']} ==")
        ra = stage_a_icrc.run(Dp, subjects, "both", cfg["seed"])
        snapshot["parity_anchor"] = {
            "model": cfg["parity_anchor_model"]["name"],
            "D": Dp,
            "seed": cfg["seed"],
            "spatial": {"mean": ra["spatial"]["mean"]},
            "spatiotemporal": {"mean": ra["spatiotemporal"]["mean"]},
            "paper": {"spatial": 0.908, "spatiotemporal": 0.978},
        }

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "emg_baseline.json"
    out.write_text(json.dumps(snapshot, indent=2))

    pid = cfg["protocol"]["id"]
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Stage B reference (Python)     spatial = {sp_m * 100:5.2f}% +/- {sp_s * 100:.2f}")
    print(f"  RTL encoder (board / export)   spatial = {rtl_cached * 100:5.2f}%  (cached)")
    if rtl_measured:
        print(
            f"  RTL encoder (recomputed)       spatial = "
            f"{rtl_measured['spatial_mean'] * 100:5.2f}%"
        )
    print(f"  Stage B spatiotemporal         = {st_m * 100:5.2f}% +/- {st_s * 100:.2f}")
    if "parity_anchor" in snapshot:
        pa = snapshot["parity_anchor"]
        print(f"  MAP anchor spatial             = {pa['spatial']['mean'] * 100:5.2f}%  (paper 90.8%)")
    print(f"\n  >>> Reference baseline  = {sp_m * 100:.2f}% +/- {sp_s * 100:.2f} (Stage B, protocol {pid})")
    print(f"  >>> RTL encoder baseline = {rtl_cached * 100:.2f}% (board verified, same protocol)")
    print(f"  snapshot -> {out}")
    return snapshot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=HERE / "config" / "emg_baseline.json")
    ap.add_argument("--no-parity", action="store_true", help="skip MAP parity anchor")
    ap.add_argument("--quick", action="store_true", help="single seed for Stage B std")
    ap.add_argument(
        "--measure-rtl-ref",
        action="store_true",
        help="recompute hdc_ref spatial (slow; use --rtl-max-windows to cap)",
    )
    ap.add_argument(
        "--rtl-max-windows",
        type=int,
        default=None,
        help="cap TEST windows per subject for --measure-rtl-ref",
    )
    args = ap.parse_args()

    t0 = time.time()
    run(
        args.config,
        run_parity=not args.no_parity,
        quick=args.quick,
        measure_rtl=args.measure_rtl_ref,
        rtl_max_windows=args.rtl_max_windows,
    )
    print(f"  total {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
