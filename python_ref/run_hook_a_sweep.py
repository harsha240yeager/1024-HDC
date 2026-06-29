#!/usr/bin/env python3
"""
Hook A — Python accuracy sweep (D × CNT_W × pruning keep ratio).

RTL-matched hdc_ref encoder on the frozen EMG protocol (P-may2026). Produces
accuracy vs configuration for the 3-axis Pareto study before board energy anchors.

Axes (research plan §9.1):
  - D ∈ {256, 512, 1024, 2048}
  - CNT_W ∈ {3, 4, 5, 6}  (bundle counter width — query encode path)
  - keep_ratio ∈ {1.0, 0.5, 0.25, 0.125}  (0 / 50 / 75 / 87.5% pruned)

Pruning: informed Fisher mask from pooled TRAIN windows (same density for all
classes). Energy on silicon comes later (INA219); this run adds energy_proxy and
optional LUT util from results/dsweep/summary.txt.

Usage (from repo root):
  python3 python_ref/run_hook_a_sweep.py --quick          # ~3 min sanity (capped windows)
  python3 python_ref/run_hook_a_sweep.py                  # full grid (hours)
  python3 python_ref/run_hook_a_sweep.py --D 1024 --keep 1.0 0.5

Outputs:
  results/hook_a/sweep_results.json
  results/hook_a/sweep_summary.csv
  results/hook_a/README.md  (auto-updated table)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import scipy.io as sio

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

from hdc_ref import (  # noqa: E402
    HDCConfig,
    HDCEngine,
    ItemMemory,
    bundle_majority_unlimited,
    mask_from_scores,
    per_bit_fisher_scores,
)
from export_emg_board_vectors import (  # noqa: E402
    DATASET,
    N_CLASS,
    level21_to_grid,
    quantize_envelope,
    require_dataset,
    split_train_test,
)

DEFAULT_SWEEP_CFG = HERE / "config" / "hook_a_sweep.json"
DEFAULT_EMG_CFG = HERE / "config" / "emg_baseline.json"
OUT_DIR = REPO / "results" / "hook_a"
DSWEEP_SUMMARY = REPO / "results" / "dsweep" / "summary.txt"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hdc_cfg_for_d(D: int, item_mem_seed: int) -> HDCConfig:
    bits_per_word = 64
    if D % bits_per_word != 0:
        raise ValueError(f"D={D} must be a multiple of {bits_per_word}")
    return HDCConfig(D=D, words=D // bits_per_word, bits_per_word=bits_per_word, seed=item_mem_seed)


def load_dsweep_lut() -> Dict[int, int]:
    """Parse Slice LUT counts from results/dsweep/synth_D*.txt if present."""
    lut: Dict[int, int] = {}
    if not DSWEEP_SUMMARY.parent.is_dir():
        return lut
    for path in sorted(DSWEEP_SUMMARY.parent.glob("synth_D*.txt")):
        try:
            d_val = int(path.stem.replace("synth_D", ""))
        except ValueError:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("| Slice LUTs"):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    lut[d_val] = int(parts[1].replace(",", ""))
                break
    return lut


def train_prototypes(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    train_q: np.ndarray,
    train_labels: np.ndarray,
    cnt_w: int,
) -> np.ndarray:
    protos = np.zeros((N_CLASS, cfg.D), dtype=np.uint8)
    for k in range(1, N_CLASS + 1):
        idx = np.where(train_labels == k)[0]
        if idx.size == 0:
            continue
        windows = [
            engine.encode_emg_window(level21_to_grid(train_q[i], cfg), mem, cnt_bits=cnt_w)
            for i in idx
        ]
        protos[k - 1] = bundle_majority_unlimited(windows, cfg)
    return protos


def encode_queries(
    engine: HDCEngine,
    mem: ItemMemory,
    cfg: HDCConfig,
    q: np.ndarray,
    cnt_w: int,
    progress_label: str = "",
) -> np.ndarray:
    n = q.shape[0]
    out = np.zeros((n, cfg.D), dtype=np.uint8)
    step = max(1, n // 20)
    for i in range(n):
        if progress_label and i > 0 and i % step == 0:
            print(f"      encode {progress_label}: {i}/{n}", flush=True)
        out[i] = engine.encode_emg_window(level21_to_grid(q[i], cfg), mem, cnt_bits=cnt_w)
    return out


def accuracy_with_mask(
    engine: HDCEngine,
    queries: np.ndarray,
    labels: np.ndarray,
    protos: np.ndarray,
    mask: np.ndarray,
) -> Tuple[float, int, int]:
    gt = labels.astype(np.int32) - 1
    correct = 0
    total = int(labels.shape[0])
    for i in range(total):
        pred = engine.classify(queries[i], protos, mask=mask).class_id
        if pred == int(gt[i]):
            correct += 1
    acc = correct / total if total else 0.0
    return acc, correct, total


def sweep_subject(
    subject: int,
    D: int,
    cnt_w: int,
    keep_ratios: Sequence[float],
    seed: int,
    train_frac: float,
    item_mem_seed: int,
    max_test_windows: Optional[int],
    max_train_windows: Optional[int],
) -> Tuple[List[dict], np.ndarray, np.ndarray]:
    mat = sio.loadmat(str(DATASET))
    data = mat[f"COMPLETE_{subject}"].astype(np.float64)
    labels = mat[f"LABEL_{subject}"].ravel().astype(np.int64)
    q_all = quantize_envelope(data)

    train_q, train_labels, test_q, test_labels = split_train_test(
        q_all, labels, train_frac, seed
    )
    if max_train_windows is not None and train_q.shape[0] > max_train_windows:
        train_q = train_q[:max_train_windows]
        train_labels = train_labels[:max_train_windows]
    if max_test_windows is not None and test_q.shape[0] > max_test_windows:
        test_q = test_q[:max_test_windows]
        test_labels = test_labels[:max_test_windows]

    cfg = hdc_cfg_for_d(D, item_mem_seed)
    mem = ItemMemory(cfg)
    engine = HDCEngine(cfg)

    print(f"    subject {subject}: train={train_q.shape[0]} test={test_q.shape[0]}", flush=True)
    train_hvs = encode_queries(engine, mem, cfg, train_q, cnt_w, f"s{subject}/train")
    test_hvs = encode_queries(engine, mem, cfg, test_q, cnt_w, f"s{subject}/test")
    protos = train_prototypes(engine, mem, cfg, train_q, train_labels, cnt_w)

    fisher_scores = per_bit_fisher_scores(train_hvs, train_labels.astype(np.int32))
    rows: List[dict] = []

    for keep in keep_ratios:
        if keep >= 1.0 - 1e-9:
            mask = np.ones(cfg.D, dtype=np.uint8)
        else:
            mask = mask_from_scores(fisher_scores, keep, informed=True)
        acc, correct, total = accuracy_with_mask(engine, test_hvs, test_labels, protos, mask)
        rows.append(
            {
                "subject": subject,
                "D": D,
                "cnt_w": cnt_w,
                "keep_ratio": keep,
                "prune_pct": round(100.0 * (1.0 - keep), 2),
                "accuracy": acc,
                "correct": correct,
                "n_test": total,
                "n_train": int(train_q.shape[0]),
            }
        )
    return rows, train_hvs, test_labels


def aggregate_rows(rows: List[dict], dsweep_lut: Dict[int, int]) -> List[dict]:
    """Mean accuracy per (D, cnt_w, keep_ratio) across subjects."""
    keys = ("D", "cnt_w", "keep_ratio")
    buckets: Dict[Tuple, List[dict]] = {}
    for r in rows:
        k = (r["D"], r["cnt_w"], r["keep_ratio"])
        buckets.setdefault(k, []).append(r)

    summary = []
    for (D, cnt_w, keep), group in sorted(buckets.items()):
        accs = [g["accuracy"] for g in group]
        mean_acc = float(np.mean(accs))
        baseline_acc = None
        if D == 1024 and cnt_w == 6 and abs(keep - 1.0) < 1e-9:
            baseline_acc = mean_acc
        lut = dsweep_lut.get(D)
        energy_proxy = (D / 1024.0) * keep
        area_proxy = (lut / dsweep_lut[1024]) if (lut and dsweep_lut.get(1024)) else None
        summary.append(
            {
                "D": D,
                "cnt_w": cnt_w,
                "keep_ratio": keep,
                "prune_pct": round(100.0 * (1.0 - keep), 2),
                "spatial_mean_accuracy": mean_acc,
                "per_subject_accuracy": {str(g["subject"]): g["accuracy"] for g in group},
                "n_test_total": sum(g["n_test"] for g in group),
                "slice_luts_ooc": lut,
                "energy_proxy_d_keep": round(energy_proxy, 4),
                "area_proxy_vs_d1024": round(area_proxy, 4) if area_proxy is not None else None,
            }
        )
    return summary


def _write_checkpoint(out_dir: Path, meta: dict, per_subject: List[dict]) -> None:
    """Append partial results so a long run is not lost if interrupted."""
    path = out_dir / "sweep_results.partial.json"
    path.write_text(
        json.dumps({"meta": meta, "per_subject": per_subject}, indent=2),
        encoding="utf-8",
    )


def write_csv(path: Path, summary: List[dict]) -> None:
    fields = [
        "D", "cnt_w", "keep_ratio", "prune_pct",
        "spatial_mean_accuracy", "energy_proxy_d_keep",
        "slice_luts_ooc", "area_proxy_vs_d1024",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in summary:
            w.writerow(row)


def write_readme(path: Path, summary: List[dict], meta: dict) -> None:
    lines = [
        "# Hook A — Python accuracy sweep (Pareto axes)",
        "",
        f"Generated: {meta['generated_at']}",
        f"Engine: **{meta['engine']}** (RTL-matched `hdc_ref` / `encoder_top.sv`)",
        f"Mask: **{meta['mask_mode']}** (Fisher-informed, train pooled per subject)",
        "",
        "Energy on silicon (INA219) is **deferred**; `energy_proxy_d_keep = (D/1024)×keep_ratio`.",
        "Area proxy from OOC synth: `results/dsweep/`.",
        "",
        "## Spatial mean accuracy (5 subjects, TEST split)",
        "",
        "| D | CNT_W | Keep | Prune % | Accuracy | Δ vs D=1024,CNT_W=6,keep=1 | Energy proxy | LUT (OOC) |",
        "|---|-------|------|---------|----------|---------------------------|--------------|-------------|",
    ]
    ref_acc = meta.get("reference_accuracy")
    for row in summary:
        acc = row["spatial_mean_accuracy"]
        delta = ""
        if ref_acc is not None:
            delta = f"{100.0 * (acc - ref_acc):+.2f} pp"
        lut = row.get("slice_luts_ooc") or "—"
        lines.append(
            f"| {row['D']} | {row['cnt_w']} | {row['keep_ratio']} | {row['prune_pct']} | "
            f"**{100.0 * acc:.2f}%** | {delta} | {row['energy_proxy_d_keep']} | {lut} |"
        )
    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```bash",
            "cd python_ref",
            "python3 run_hook_a_sweep.py --quick    # sanity (~3 min, capped windows)",
            "python3 run_hook_a_sweep.py            # full grid (hours)",
            "```",
            "",
            "Full JSON: `sweep_results.json`, CSV: `sweep_summary.csv`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hook A Python Pareto accuracy sweep")
    p.add_argument("--config", type=Path, default=DEFAULT_SWEEP_CFG)
    p.add_argument("--emg-config", type=Path, default=DEFAULT_EMG_CFG)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--quick", action="store_true", help="small grid from config quick section")
    p.add_argument("--D", type=int, nargs="*", help="override D list")
    p.add_argument("--cnt-w", type=int, nargs="*", dest="cnt_w", help="override CNT_W list")
    p.add_argument("--keep", type=float, nargs="*", help="override keep_ratio list")
    p.add_argument("--max-windows", type=int, default=None, help="cap TEST windows per subject")
    p.add_argument("--max-train-windows", type=int, default=None, help="cap TRAIN windows per subject")
    p.add_argument("--subjects", type=int, nargs="*", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_dataset()

    sweep_cfg = load_json(args.config)
    emg_cfg = load_json(args.emg_config)

    if args.quick:
        q = sweep_cfg["quick"]
        d_list = q["D_list"]
        cnt_list = q["cnt_w_list"]
        keep_list = q["keep_ratio_list"]
        max_windows = q.get("max_test_windows_per_subject")
        max_train_windows = q.get("max_train_windows_per_subject")
        subjects = args.subjects or q.get("subjects") or sweep_cfg["subjects"]
    else:
        d_list = args.D or sweep_cfg["D_list"]
        cnt_list = args.cnt_w or sweep_cfg["cnt_w_list"]
        keep_list = args.keep or sweep_cfg["keep_ratio_list"]
        max_windows = args.max_windows
        max_train_windows = args.max_train_windows
        subjects = args.subjects or sweep_cfg["subjects"]
    seed = int(emg_cfg["seed"])
    train_frac = float(emg_cfg["protocol"]["train_fraction"])
    item_mem_seed = int(sweep_cfg["item_mem_seed"])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    dsweep_lut = load_dsweep_lut()

    print("=" * 70)
    print("Hook A Python sweep (hdc_ref / RTL encoder)")
    print(f"  D: {d_list}  CNT_W: {cnt_list}  keep: {keep_list}")
    print(f"  subjects: {subjects}")
    print(f"  max_train_windows: {max_train_windows or 'all'}  max_test_windows: {max_windows or 'all'}")
    print("=" * 70)

    t0 = time.time()
    all_rows: List[dict] = []

    for D in d_list:
        for cnt_w in cnt_list:
            print(f"\n== D={D} CNT_W={cnt_w} ==", flush=True)
            for subject in subjects:
                rows, _, _ = sweep_subject(
                    subject, D, cnt_w, keep_list, seed, train_frac,
                    item_mem_seed, max_windows, max_train_windows,
                )
                all_rows.extend(rows)
                _write_checkpoint(args.out_dir, meta={
                    "status": "running",
                    "last": {"D": D, "cnt_w": cnt_w, "subject": subject},
                }, per_subject=all_rows)

    summary = aggregate_rows(all_rows, dsweep_lut)
    ref_row = next(
        (s for s in summary if s["D"] == 1024 and s["cnt_w"] == 6 and s["keep_ratio"] == 1.0),
        None,
    )
    ref_acc = ref_row["spatial_mean_accuracy"] if ref_row else None

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine": sweep_cfg["engine"],
        "mask_mode": sweep_cfg["mask_mode"],
        "protocol": emg_cfg["protocol"]["id"],
        "subjects": subjects,
        "D_list": d_list,
        "cnt_w_list": cnt_list,
        "keep_ratio_list": keep_list,
        "max_train_windows_per_subject": max_train_windows,
        "max_test_windows_per_subject": max_windows,
        "elapsed_s": round(time.time() - t0, 1),
        "reference_accuracy": ref_acc,
        "board_rtl_baseline_D1024": sweep_cfg.get("board_rtl_baseline_accuracy"),
    }

    out_json = args.out_dir / "sweep_results.json"
    out_csv = args.out_dir / "sweep_summary.csv"
    out_readme = args.out_dir / "README.md"

    payload = {"meta": meta, "per_subject": all_rows, "summary": summary}
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(out_csv, summary)
    write_readme(out_readme, summary, meta)

    print("\n" + "=" * 70)
    print(f"Done in {meta['elapsed_s']:.1f}s")
    print(f"  {out_json}")
    print(f"  {out_csv}")
    print(f"  {out_readme}")
    if ref_acc is not None:
        print(f"  Reference (D=1024, CNT_W=6, keep=1.0): {100.0 * ref_acc:.2f}%")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
