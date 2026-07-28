#!/usr/bin/env python3
"""
Phase 0 — Stage B spatial baseline under Protocol HDC-2.

Full-width (unpruned) accuracy on the literature BSC encoder path using the
same disjoint train/test split as hdc_ref / board replay.

Usage (from repo root):
  python3 python_ref/run_stage_b_baseline.py
  python3 python_ref/run_stage_b_baseline.py --quick

Outputs:
  results/protocol_v2/stage_b_hdc2/baseline.json
  results/protocol_v2/stage_b_hdc2/README.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from export_emg_board_vectors import DATASET, require_dataset  # noqa: E402
from stage_b_engine import eval_subject, load_json, split_config_from_emg  # noqa: E402

DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline_v2.json"
OUT_DIR = REPO / "results" / "protocol_v2" / "stage_b_hdc2"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage B HDC-2 spatial baseline")
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--D", type=int, default=1024)
    p.add_argument("--item-mem-seed", type=int, default=None)
    p.add_argument("--quick", action="store_true", help="subject 1 only")
    p.add_argument("--verify-mask", action="store_true", help="assert full mask == legacy predict path")
    return p.parse_args()


def verify_masked_matches_legacy(result: dict) -> None:
    """Sanity: full-mask classify matches stage_b_bsc bipolar predict."""
    from repro.stage_b_bsc import predict, train_prototypes as legacy_train_prototypes

    train_hvs = result["train_hvs"]
    test_hvs = result["test_hvs"]
    train_labels = result["train_labels"]
    test_labels = result["test_labels"]
    d = train_hvs.shape[1]

    p_legacy = legacy_train_prototypes(train_hvs, train_labels, d)
    pred_legacy = predict(test_hvs, p_legacy)
    acc_legacy = float(np.mean(pred_legacy == test_labels))
    if abs(acc_legacy - result["accuracy"]) > 1e-9:
        raise AssertionError(
            f"masked full-width {result['accuracy']:.6f} != legacy predict {acc_legacy:.6f}"
        )


def write_readme(path: Path, meta: dict, per_subject: list, mean_acc: float) -> None:
    lines = [
        "# Stage B spatial baseline — Protocol HDC-2",
        "",
        f"Generated: {meta['generated_at']}",
        f"Engine: Stage B BSC (4-channel spatial records, D={meta['D']})",
        f"Protocol: **{meta['protocol']}** · item-memory seed **{meta['item_mem_seed']}**",
        "",
        "## Headline (5-subject spatial mean)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Spatial mean accuracy | **{100.0 * mean_acc:.2f}%** |",
        "",
        "## Per subject",
        "",
        "| Subject | Train | Test | Accuracy |",
        "|---------|-------|------|----------|",
    ]
    for row in per_subject:
        lines.append(
            f"| S{row['subject']} | {row['n_train']} | {row['n_test']} | "
            f"{100.0 * row['accuracy']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 python_ref/run_stage_b_baseline.py",
            "python3 python_ref/run_stage_b_baseline.py --quick",
            "```",
            "",
            "Phase 1 masked engine: `python_ref/stage_b_engine.py`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    require_dataset()
    emg_cfg = load_json(args.emg_config)
    seed, train_frac, split_kw, subjects = split_config_from_emg(emg_cfg)
    item_mem_seed = int(args.item_mem_seed if args.item_mem_seed is not None else seed)

    if args.quick:
        subjects = [subjects[0]]

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Stage B spatial baseline — Protocol HDC-2")
    print(f"  subjects={subjects}  D={args.D}  item_mem_seed={item_mem_seed}")
    print(f"  protocol={emg_cfg['protocol']['id']}  dataset={DATASET}")
    print("=" * 70)

    t0 = time.time()
    per_subject = []
    for sid in subjects:
        print(f"\n== subject {sid} ==", flush=True)
        result = eval_subject(
            sid,
            seed=seed,
            train_frac=train_frac,
            split_kw=split_kw,
            item_mem_seed=item_mem_seed,
            D=args.D,
        )
        if args.verify_mask:
            verify_masked_matches_legacy(result)
            print("    verify: full mask matches legacy predict", flush=True)

        row = {k: result[k] for k in ("subject", "n_train", "n_test", "correct", "accuracy")}
        per_subject.append(row)
        print(f"    accuracy={100.0 * row['accuracy']:.2f}%", flush=True)

    mean_acc = float(np.mean([r["accuracy"] for r in per_subject]))
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": emg_cfg["protocol"]["id"],
        "D": args.D,
        "item_mem_seed": item_mem_seed,
        "split_seed": seed,
        "train_fraction": train_frac,
        "dataset": str(DATASET.resolve()),
        "elapsed_s": round(time.time() - t0, 1),
        "spatial_mean_accuracy": mean_acc,
    }
    payload = {"meta": meta, "per_subject": per_subject}
    out_json = args.out_dir / "baseline.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_readme(args.out_dir / "README.md", meta, per_subject, mean_acc)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    print(f"  Stage B HDC-2 spatial mean: {100.0 * mean_acc:.2f}%")
    print(f"  {out_json}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
