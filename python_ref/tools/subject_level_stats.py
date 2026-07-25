#!/usr/bin/env python3
"""
Subject-level paired statistics for iso-density (Twist 1) gaps.

Unit of analysis = subject (never windows). Bootstrap CI and Wilcoxon /
paired t-test are computed over the per-subject gap vector
(informed − random), in percentage points.

Usage (from repo root):
  python3 python_ref/tools/subject_level_stats.py \\
      --results results/protocol_v2/twist1_keep0125_30seed/twist1_results.json

Outputs (next to the results JSON by default):
  subject_level_stats.json
  subject_level_stats.md  (also updates parent README section if present)
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:  # pragma: no cover
    scipy_stats = None


def bootstrap_ci(
    values: np.ndarray,
    *,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
    statistic: str = "mean",
) -> Tuple[float, float, float]:
    """Percentile bootstrap CI over the subject vector."""
    x = np.asarray(values, dtype=np.float64).ravel()
    if x.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n = x.size
    boots = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        sample = rng.choice(x, size=n, replace=True)
        boots[i] = float(np.mean(sample) if statistic == "mean" else np.median(sample))
    lo = float(np.percentile(boots, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(boots, 100.0 * (1.0 - alpha / 2.0)))
    point = float(np.mean(x) if statistic == "mean" else np.median(x))
    return point, lo, hi


def wilcoxon_tests(gaps_pp: np.ndarray) -> Dict[str, Any]:
    """Paired Wilcoxon on per-subject gaps (informed − random > 0)."""
    g = np.asarray(gaps_pp, dtype=np.float64).ravel()
    out: Dict[str, Any] = {
        "n_subjects": int(g.size),
        "n_positive": int(np.sum(g > 0)),
        "n_negative": int(np.sum(g < 0)),
        "n_zero": int(np.sum(g == 0)),
    }
    if scipy_stats is None or g.size < 2:
        out["available"] = False
        out["reason"] = "scipy missing or n<2"
        return out
    out["available"] = True
    # Exact for small n; zero_method='wilcox' drops zeros
    for alt, key in (("two-sided", "two_sided"), ("greater", "greater")):
        try:
            res = scipy_stats.wilcoxon(
                g, alternative=alt, zero_method="wilcox", method="auto"
            )
            out[f"wilcoxon_{key}_statistic"] = float(res.statistic)
            out[f"wilcoxon_{key}_pvalue"] = float(res.pvalue)
        except ValueError as exc:
            out[f"wilcoxon_{key}_error"] = str(exc)
    try:
        tres = scipy_stats.ttest_1samp(g, popmean=0.0, alternative="greater")
        out["paired_t_greater_statistic"] = float(tres.statistic)
        out["paired_t_greater_pvalue"] = float(tres.pvalue)
        tres2 = scipy_stats.ttest_1samp(g, popmean=0.0, alternative="two-sided")
        out["paired_t_two_sided_statistic"] = float(tres2.statistic)
        out["paired_t_two_sided_pvalue"] = float(tres2.pvalue)
    except Exception as exc:  # noqa: BLE001
        out["paired_t_error"] = str(exc)
    return out


def gaps_from_twist1(per_subject: Sequence[dict]) -> Tuple[np.ndarray, List[dict]]:
    rows = []
    gaps = []
    for row in per_subject:
        gap = float(row["gap_pp_mean"])
        gaps.append(gap)
        rows.append(
            {
                "subject": int(row["subject"]),
                "informed_accuracy": float(row["informed_accuracy"]),
                "random_accuracy_mean": float(row["random_accuracy_mean"]),
                "gap_pp": gap,
                "n_test": int(row.get("n_test", 0)),
            }
        )
    return np.asarray(gaps, dtype=np.float64), rows


def summarize_subject_gaps(
    gaps_pp: np.ndarray,
    *,
    n_boot: int = 10_000,
    seed: int = 0,
    target_gap_pp: float = 5.0,
) -> Dict[str, Any]:
    g = np.asarray(gaps_pp, dtype=np.float64).ravel()
    mean_gap, ci_lo, ci_hi = bootstrap_ci(g, n_boot=n_boot, seed=seed, statistic="mean")
    med_gap, med_lo, med_hi = bootstrap_ci(g, n_boot=n_boot, seed=seed + 1, statistic="median")
    tests = wilcoxon_tests(g)
    return {
        "n_subjects": int(g.size),
        "unit_of_analysis": "subject",
        "note": "Bootstrap and hypothesis tests are over subjects, not windows.",
        "gap_pp_mean": mean_gap,
        "gap_pp_median": float(np.median(g)),
        "gap_pp_std": float(np.std(g, ddof=1)) if g.size > 1 else 0.0,
        "gap_pp_min": float(np.min(g)),
        "gap_pp_max": float(np.max(g)),
        "bootstrap_mean_95ci_pp": [ci_lo, ci_hi],
        "bootstrap_median_95ci_pp": [med_lo, med_hi],
        "bootstrap_n": n_boot,
        "bootstrap_seed": seed,
        "target_gap_pp": target_gap_pp,
        "target_met_by_mean": bool(mean_gap >= target_gap_pp),
        "ci_excludes_zero": bool(ci_lo > 0.0),
        "ci_excludes_target": bool(ci_lo >= target_gap_pp),
        "tests": tests,
    }


def analyze_twist1_results(
    path: Path,
    *,
    n_boot: int = 10_000,
    seed: int = 0,
) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    gaps, rows = gaps_from_twist1(data["per_subject"])
    target = float(meta.get("target_gap_pp", 5.0))
    summary = summarize_subject_gaps(gaps, n_boot=n_boot, seed=seed, target_gap_pp=target)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(path).replace("\\", "/"),
        "protocol": meta.get("protocol", "HDC-2"),
        "keep_ratio": meta.get("keep_ratio"),
        "n_keep": meta.get("n_keep"),
        "n_random_seeds": len(meta.get("random_seeds", [])),
        "mean_informed_accuracy": meta.get("mean_informed_accuracy"),
        "mean_random_accuracy": meta.get("mean_random_accuracy"),
        "per_subject": rows,
        "summary": summary,
    }


def format_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    t = s["tests"]
    lines = [
        "# Subject-level statistics (Twist 1 iso-density)",
        "",
        f"Source: `{report['source']}`",
        f"Generated: {report['generated_at']}",
        f"Protocol: **{report['protocol']}** · keep={report['keep_ratio']} "
        f"({report['n_keep']} bits) · {report['n_random_seeds']} random seeds",
        "",
        f"**Unit of analysis: subject (n={s['n_subjects']})** — not windows.",
        "",
        "## Paired gap (informed − random), percentage points",
        "",
        f"| Statistic | Value |",
        f"|-----------|-------|",
        f"| Mean gap | **{s['gap_pp_mean']:+.2f} pp** |",
        f"| Median gap | {s['gap_pp_median']:+.2f} pp |",
        f"| Std (sample) | {s['gap_pp_std']:.2f} pp |",
        f"| Min / max | {s['gap_pp_min']:+.2f} / {s['gap_pp_max']:+.2f} pp |",
        f"| Bootstrap 95% CI (mean) | [{s['bootstrap_mean_95ci_pp'][0]:+.2f}, "
        f"{s['bootstrap_mean_95ci_pp'][1]:+.2f}] pp |",
        f"| CI excludes 0? | {'yes' if s['ci_excludes_zero'] else 'no'} |",
        f"| Target (≥ {s['target_gap_pp']:g} pp) met by mean? | "
        f"{'yes' if s['target_met_by_mean'] else 'no'} |",
        "",
        "## Hypothesis tests (paired over subjects)",
        "",
    ]
    if t.get("available"):
        p2 = t.get("wilcoxon_two_sided_pvalue")
        p1 = t.get("wilcoxon_greater_pvalue")
        pt1 = t.get("paired_t_greater_pvalue")
        lines.append(
            f"- Subjects with positive gap: **{t['n_positive']}/{t['n_subjects']}**"
        )
        lines.append(
            f"- Wilcoxon signed-rank (two-sided): p = {p2:.4g}"
            if p2 is not None
            else "- Wilcoxon two-sided: n/a"
        )
        lines.append(
            f"- Wilcoxon signed-rank (one-sided, greater): p = {p1:.4g}"
            if p1 is not None
            else "- Wilcoxon greater: n/a"
        )
        lines.append(
            f"- Paired t-test (one-sided, greater): p = {pt1:.4g}"
            if pt1 is not None
            else "- Paired t greater: n/a"
        )
        lines.extend(
            [
                "",
                "With n=5, the exact two-sided Wilcoxon floor when all gaps are "
                "positive is 1/16 = 0.0625; one-sided floor is 1/32 = 0.03125. "
                "Report the CI and the 5/5 positive-gap count alongside p-values.",
            ]
        )
    else:
        lines.append(f"- Tests unavailable: {t.get('reason', 'unknown')}")

    lines.extend(
        [
            "",
            "## Per-subject gaps",
            "",
            "| Subject | Informed | Random mean | Gap (pp) |",
            "|---------|----------|-------------|----------|",
        ]
    )
    for row in report["per_subject"]:
        lines.append(
            f"| S{row['subject']} | {100.0 * row['informed_accuracy']:.2f}% | "
            f"{100.0 * row['random_accuracy_mean']:.2f}% | {row['gap_pp']:+.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Subject-level Twist 1 statistics")
    p.add_argument(
        "--results",
        type=Path,
        default=Path("results/protocol_v2/twist1_keep0125_30seed/twist1_results.json"),
    )
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--n-boot", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    results_path = args.results
    if not results_path.is_file():
        raise SystemExit(f"results not found: {results_path}")
    out_dir = args.out_dir or results_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    report = analyze_twist1_results(results_path, n_boot=args.n_boot, seed=args.seed)
    json_path = out_dir / "subject_level_stats.json"
    md_path = out_dir / "subject_level_stats.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(format_md(report), encoding="utf-8")

    # Append / refresh a section in the Twist 1 README if present
    readme = out_dir / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        marker = "## Subject-level statistics"
        block = format_md(report).split("\n", 1)[1]  # drop top title
        section = marker + "\n" + block
        if marker in text:
            # Replace from marker to next ## or end
            pre, rest = text.split(marker, 1)
            if "\n## " in rest:
                _, post = rest.split("\n## ", 1)
                text = pre.rstrip() + "\n\n" + section.rstrip() + "\n\n## " + post
            else:
                text = pre.rstrip() + "\n\n" + section.rstrip() + "\n"
        else:
            # Insert before ## Regenerate if present
            if "## Regenerate" in text:
                pre, post = text.split("## Regenerate", 1)
                text = pre.rstrip() + "\n\n" + section.rstrip() + "\n\n## Regenerate" + post
            else:
                text = text.rstrip() + "\n\n" + section.rstrip() + "\n"
        readme.write_text(text, encoding="utf-8")

    s = report["summary"]
    print("=" * 60)
    print("Subject-level stats (unit = subject)")
    print(
        f"  mean gap = {s['gap_pp_mean']:+.2f} pp  "
        f"95% CI [{s['bootstrap_mean_95ci_pp'][0]:+.2f}, "
        f"{s['bootstrap_mean_95ci_pp'][1]:+.2f}]"
    )
    t = s["tests"]
    if t.get("available"):
        print(
            f"  Wilcoxon two-sided p = {t.get('wilcoxon_two_sided_pvalue'):.4g}  "
            f"one-sided p = {t.get('wilcoxon_greater_pvalue'):.4g}  "
            f"positive = {t['n_positive']}/{t['n_subjects']}"
        )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
