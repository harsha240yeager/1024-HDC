#!/usr/bin/env python3
"""Issue #41 — LUT hierarchy + core cycles from committed Vivado reports (no new P&R)."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "protocol_v2" / "lut_hierarchy"

REPORTS = {
    "baseline_core_ooc": REPO / "results/dsweep/synth_baseline_core.txt",
    "narrow_core_ooc": REPO / "results/dsweep/synth_narrow_core.txt",
    "baseline_stream_ooc": REPO / "results/dsweep/synth_baseline_stream.txt",
    "narrow_stream_ooc": REPO / "results/dsweep/synth_narrow_stream.txt",
    "baseline_bd_ooc": REPO / "results/dsweep/synth_baseline_bd.txt",
    "narrow_bd_ooc": REPO / "results/dsweep/synth_narrow_bd.txt",
    "narrow_integrated_placed": REPO / "results/narrow_rtl/integrated_utilization_placed.rpt",
}


def parse_hierarchy_rows(text: str) -> list[dict]:
    """Parse Vivado 'Utilization by Hierarchy' table rows."""
    rows: list[dict] = []
    in_table = False
    for line in text.splitlines():
        if "Utilization by Hierarchy" in line and "Table of Contents" not in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("+---") and rows:
            break
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if parts[0] in ("Instance", "-------"):
            continue
        if len(parts) < 6:
            continue
        try:
            luts = int(parts[2].replace(",", ""))
        except ValueError:
            continue
        rows.append(
            {
                "instance": parts[0],
                "module": parts[1],
                "luts": luts,
                "ffs": int(parts[5].replace(",", "")) if parts[5].replace(",", "").isdigit() else None,
            }
        )
    return rows


def parse_slice_luts(text: str) -> int | None:
    for line in text.splitlines():
        if "Slice LUTs" in line and line.strip().startswith("|"):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and parts[0].startswith("Slice LUT"):
                try:
                    return int(parts[1].replace(",", ""))
                except ValueError:
                    pass
    return None


def parse_timing_wns_whs(text: str) -> dict:
    """First timing summary row after 'Design timing summary' or WNS(ns) header."""
    wns = whs = None
    for i, line in enumerate(text.splitlines()):
        if "WNS(ns)" in line and "TNS(ns)" in line:
            for nxt in text.splitlines()[i + 1 : i + 6]:
                if nxt.strip().startswith("---"):
                    continue
                cols = [c.strip() for c in nxt.split() if c.strip()]
                if len(cols) >= 5:
                    try:
                        wns = float(cols[0])
                        whs = float(cols[4])
                        return {"wns_ns": wns, "whs_ns": whs}
                    except ValueError:
                        continue
        if "Setup :" in line and "Worst Slack" in line:
            m = re.search(r"Worst Slack\s+([\d.]+)ns", line)
            if m:
                wns = float(m.group(1))
    return {"wns_ns": wns, "whs_ns": whs}


def find_row(rows: list[dict], instance: str) -> dict | None:
    for r in rows:
        if r["instance"].strip() == instance:
            return r
    return None


def core_cycle_model(*, words: int, k_words: int, n_class: int = 8, n_pairs: int = 20) -> dict:
    encode = n_pairs + 3
    classify = n_class * (2 * words + 1)
    classify_narrow = n_class * (2 * k_words + 1)
    return {
        "n_pairs": n_pairs,
        "n_class_slots": n_class,
        "encode_cycles": encode,
        "classify_cycles_full": classify,
        "classify_cycles_narrow": classify_narrow,
        "total_cycles_full": encode + classify,
        "total_cycles_narrow": encode + classify_narrow,
        "at_100mhz_us_full": round((encode + classify) * 0.01, 2),
        "at_100mhz_us_narrow": round((encode + classify_narrow) * 0.01, 2),
        "note": "RTL uses N_CLASS=8 slots; EMG deploys 5 active prototypes.",
    }


def parse_bench_us(path: Path) -> dict:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    single = re.search(r"Single-window DMA latency[\s\S]*?mean\s*=\s*(\d+)\s*us", text)
    batch = re.search(r"mean/window ~ (\d+) us", text)
    batch_total = re.search(r"Batch duration \(ms\):\s*([\d.]+)", text)
    batch_n = re.search(r"Batch windows:\s*(\d+)", text)
    out = {}
    if single:
        out["single_window_dma_mean_us"] = int(single.group(1))
    if batch:
        out["batch_200_mean_us_per_window"] = int(batch.group(1))
    elif batch_total and batch_n:
        out["batch_200_mean_us_per_window"] = round(
            float(batch_total.group(1)) * 1000 / int(batch_n.group(1)), 2
        )
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    parsed: dict[str, list[dict]] = {}
    for key, path in REPORTS.items():
        if not path.is_file():
            raise SystemExit(f"missing report: {path}")
        parsed[key] = parse_hierarchy_rows(path.read_text(encoding="utf-8", errors="replace"))

    b_core = parsed["baseline_core_ooc"]
    n_core = parsed["narrow_core_ooc"]
    b_stream = parsed["baseline_stream_ooc"]
    n_stream = parsed["narrow_stream_ooc"]
    b_bd = parsed["baseline_bd_ooc"]
    n_bd = parsed["narrow_bd_ooc"]

    def bucket_core(rows: list[dict], *, narrow: bool) -> dict:
        enc = find_row(rows, "u_encoder") or find_row(rows, "u_encoder ")
        am = find_row(rows, "u_am")
        bundle = find_row(rows, "u_bundle")
        mask = find_row(rows, "u_mask")
        top = rows[0]["luts"] if rows else 0
        enc_lut = enc["luts"] if enc else 0
        am_lut = am["luts"] if am else 0
        bundle_lut = bundle["luts"] if bundle else 0
        mask_lut = mask["luts"] if mask else 0
        ctrl_lut = enc_lut - bundle_lut if enc and bundle else enc_lut
        return {
            "core_total_luts": top,
            "encoder_total_luts": enc_lut,
            "encoder_bundle_luts": bundle_lut,
            "encoder_control_luts": max(0, ctrl_lut),
            "popcount_am_luts": am_lut,
            "pruning_mask_luts": mask_lut if not narrow else 0,
            "other_core_luts": max(0, top - enc_lut - am_lut - (mask_lut if not narrow else 0)),
        }

    baseline_core = bucket_core(b_core, narrow=False)
    narrow_core = bucket_core(n_core, narrow=True)

    stream_shell = {
        "baseline": (find_row(b_stream, "(hdc_stream_wrapper)") or {}).get("luts"),
        "narrow": (find_row(n_stream, "(hdc_stream_wrapper_narrow)") or {}).get("luts"),
    }
    bd_axi_cfg = {
        "baseline": (find_row(b_bd, "u_cfg") or {}).get("luts"),
        "narrow": (find_row(n_bd, "u_cfg") or {}).get("luts"),
    }

    integrated = {
        "baseline_placed_lut": 35206,
        "narrow_placed_lut": parse_slice_luts(
            REPORTS["narrow_integrated_placed"].read_text(encoding="utf-8")
        ),
        "source_baseline": "Phase 3 deployed bitstream / board_eval_summary.json",
        "source_narrow": str(REPORTS["narrow_integrated_placed"].relative_to(REPO)),
    }
    narrow_timing_log = REPO / "results/narrow_rtl/integrated_synth.log"
    narrow_post_route_wns = None
    if narrow_timing_log.is_file():
        m = re.search(
            r"Post Routing Timing Summary \| WNS=([\d.]+)", narrow_timing_log.read_text()
        )
        if m:
            narrow_post_route_wns = float(m.group(1))

    timing = {
        "ooc_synth_baseline_core": parse_timing_wns_whs(
            REPORTS["baseline_core_ooc"].read_text(encoding="utf-8")
        ),
        "ooc_synth_narrow_core": parse_timing_wns_whs(
            REPORTS["narrow_core_ooc"].read_text(encoding="utf-8")
        ),
        "ooc_synth_baseline_bd": parse_timing_wns_whs(
            REPORTS["baseline_bd_ooc"].read_text(encoding="utf-8")
        ),
        "ooc_synth_narrow_bd": parse_timing_wns_whs(
            REPORTS["narrow_bd_ooc"].read_text(encoding="utf-8")
        ),
        "narrow_integrated_post_route_wns_ns": narrow_post_route_wns,
    }

    cycles = core_cycle_model(words=16, k_words=2)
    latency = {
        "baseline_phase3": parse_bench_us(REPO / "results/phase3/board_bench.txt"),
        "narrow_phase3": parse_bench_us(REPO / "results/protocol_v2/narrow_rtl/board_bench.txt"),
        "phase1_axi_lite_poll_us": 3,
        "note": "Batch µs/window amortizes DMA descriptor ring; single-window includes full SG path.",
    }

    ratio = baseline_core["core_total_luts"] / narrow_core["core_total_luts"]

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "issue": 41,
            "device": "xc7z020clg484-1",
            "clock_mhz": 100,
            "reports": {k: str(v.relative_to(REPO)) for k, v in REPORTS.items()},
        },
        "ooc_core_lut": {
            "baseline_hdc_core_top": baseline_core,
            "narrow_hdc_core_top_narrow": narrow_core,
            "lut_reduction_factor": round(ratio, 2),
        },
        "ooc_stream_wrapper": {
            "baseline_total": (find_row(b_stream, "hdc_stream_wrapper") or {}).get("luts"),
            "narrow_total": (find_row(n_stream, "hdc_stream_wrapper_narrow") or {}).get("luts"),
            "stream_fsm_shell_luts": stream_shell,
        },
        "ooc_bd_wrapper": {
            "baseline_total": (find_row(b_bd, "hdc_stream_system_bd_wrapper") or {}).get("luts"),
            "narrow_total": (find_row(n_bd, "hdc_stream_system_bd_wrapper_narrow") or {}).get(
                "luts"
            ),
            "axi_lite_cfg_luts": bd_axi_cfg,
        },
        "integrated_placed": integrated,
        "timing": timing,
        "core_cycles": cycles,
        "board_latency": latency,
    }

    (OUT / "lut_hierarchy_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_rows = [
        ["scope", "variant", "block", "luts"],
        ["ooc_core", "baseline", "core_total", baseline_core["core_total_luts"]],
        ["ooc_core", "baseline", "encoder", baseline_core["encoder_total_luts"]],
        ["ooc_core", "baseline", "encoder_bundle", baseline_core["encoder_bundle_luts"]],
        ["ooc_core", "baseline", "popcount_am", baseline_core["popcount_am_luts"]],
        ["ooc_core", "baseline", "pruning_mask", baseline_core["pruning_mask_luts"]],
        ["ooc_core", "narrow", "core_total", narrow_core["core_total_luts"]],
        ["ooc_core", "narrow", "encoder", narrow_core["encoder_total_luts"]],
        ["ooc_core", "narrow", "encoder_bundle", narrow_core["encoder_bundle_luts"]],
        ["ooc_core", "narrow", "popcount_am_narrow", narrow_core["popcount_am_luts"]],
        ["integrated_placed", "baseline", "design_1_wrapper", integrated["baseline_placed_lut"]],
        ["integrated_placed", "narrow", "design_1_wrapper", integrated["narrow_placed_lut"]],
    ]
    with (OUT / "lut_hierarchy_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(csv_rows)

    readme = f"""# Issue 41 — LUT hierarchy and core cycles (full vs narrow)

Generated from committed Vivado OOC synth reports (`results/dsweep/`) and narrow
integrated utilization (`results/narrow_rtl/integrated_utilization_placed.rpt`).
No new place-and-route run.

## OOC core LUT (`hdc_core_top` vs `hdc_core_top_narrow`)

| Block | Baseline (D=1024) | Narrow (K=128 AM) |
|-------|-------------------|-------------------|
| **Core total** | **{baseline_core['core_total_luts']:,}** | **{narrow_core['core_total_luts']:,}** ({ratio:.1f}× smaller) |
| Encoder (`encoder_top`) | {baseline_core['encoder_total_luts']:,} | {narrow_core['encoder_total_luts']:,} |
| — bundle (`bundle_unit`) | {baseline_core['encoder_bundle_luts']:,} | {narrow_core['encoder_bundle_luts']:,} |
| Associative memory | {baseline_core['popcount_am_luts']:,} (`popcount_am`) | {narrow_core['popcount_am_luts']:,} (`popcount_am_narrow`) |
| Pruning mask | {baseline_core['pruning_mask_luts']:,} | 0 (baked gather) |

Encoder width stays D=1024 in both bitstreams; the narrow win is almost entirely in the AM
({baseline_core['popcount_am_luts']:,} → {narrow_core['popcount_am_luts']:,} LUT) plus dropping `pruning_mask`.

## Stream + BD OOC (DMA path shell)

| Scope | Baseline LUT | Narrow LUT |
|-------|--------------|------------|
| `hdc_stream_wrapper*` | {payload['ooc_stream_wrapper']['baseline_total']:,} | {payload['ooc_stream_wrapper']['narrow_total']:,} |
| Stream FSM shell | {stream_shell['baseline']:,} | {stream_shell['narrow']:,} |
| BD wrapper + AXI cfg | {payload['ooc_bd_wrapper']['baseline_total']:,} | {payload['ooc_bd_wrapper']['narrow_total']:,} |
| — AXI-Lite cfg block | {bd_axi_cfg['baseline']:,} | {bd_axi_cfg['narrow']:,} |

## Integrated placed (Zynq PL)

| Bitstream | Slice LUTs | Source |
|-----------|------------|--------|
| Baseline Phase 3 | **{integrated['baseline_placed_lut']:,}** | Deployed design / issue #31 summary |
| Narrow (anchor C) | **{integrated['narrow_placed_lut']:,}** | `integrated_utilization_placed.rpt` |

## Core cycles @ 100 MHz (PL compute only)

| Path | Encode | Classify | **Total cycles** | **≈ µs** |
|------|--------|----------|------------------|----------|
| Baseline D=1024 | {cycles['encode_cycles']} | {cycles['classify_cycles_full']} | **{cycles['total_cycles_full']}** | {cycles['at_100mhz_us_full']} |
| Narrow K=128 AM | {cycles['encode_cycles']} | {cycles['classify_cycles_narrow']} | **{cycles['total_cycles_narrow']}** | {cycles['at_100mhz_us_narrow']} |

Classify formula: `N_CLASS × (2×WORDS + 1)` vs `N_CLASS × (2×K_WORDS + 1)` per `hdc_core_top*.sv`.

## Timing (WNS / WHS, OOC synth)

| Report | WNS (ns) | WHS (ns) |
|--------|----------|----------|
| Baseline core | {timing['ooc_synth_baseline_core'].get('wns_ns')} | {timing['ooc_synth_baseline_core'].get('whs_ns')} |
| Narrow core | {timing['ooc_synth_narrow_core'].get('wns_ns')} | {timing['ooc_synth_narrow_core'].get('whs_ns')} |
| Narrow integrated post-route | {narrow_post_route_wns} | (see integrated_synth.log) |

## Board latency (system, not core-only)

| Metric | Baseline | Narrow |
|--------|----------|--------|
| Single-window DMA mean | {latency['baseline_phase3'].get('single_window_dma_mean_us')} µs | {latency['narrow_phase3'].get('single_window_dma_mean_us')} µs |
| Batch 200 windows mean | ~{latency['baseline_phase3'].get('batch_200_mean_us_per_window')} µs/w | ~{latency['narrow_phase3'].get('batch_200_mean_us_per_window')} µs/w |
| Phase 1 AXI-Lite poll (ref) | ~{latency['phase1_axi_lite_poll_us']} µs/w | same |

## Regenerate

```bash
python3 scripts/build_lut_hierarchy_issue41.py
```
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    paper = f"""# Issue #41 — paper table (body text)

| Quantity | Baseline (D=1024) | Narrow (K=128 gather) |
|----------|-------------------|------------------------|
| OOC core LUT | {baseline_core['core_total_luts']:,} | {narrow_core['core_total_luts']:,} ({ratio:.1f}×) |
| — encoder | {baseline_core['encoder_total_luts']:,} | {narrow_core['encoder_total_luts']:,} |
| — popcount AM | {baseline_core['popcount_am_luts']:,} | {narrow_core['popcount_am_luts']:,} |
| Integrated PL LUT | {integrated['baseline_placed_lut']:,} | {integrated['narrow_placed_lut']:,} |
| Core cycles / window | {cycles['total_cycles_full']} | {cycles['total_cycles_narrow']} |
| Core time @ 100 MHz | {cycles['at_100mhz_us_full']} µs | {cycles['at_100mhz_us_narrow']} µs |
| Batch DMA latency | ~{latency['baseline_phase3'].get('batch_200_mean_us_per_window')} µs/w | ~{latency['narrow_phase3'].get('batch_200_mean_us_per_window')} µs/w |
| Single-window DMA | ~{latency['baseline_phase3'].get('single_window_dma_mean_us')} µs | ~{latency['narrow_phase3'].get('single_window_dma_mean_us')} µs |

OOC core WNS: baseline **{timing['ooc_synth_baseline_core'].get('wns_ns')} ns**; narrow core **{timing['ooc_synth_narrow_core'].get('wns_ns')} ns** (post-synth, 100 MHz constraint).
"""
    (OUT / "paper_table.md").write_text(paper, encoding="utf-8")

    print(f"Wrote {OUT / 'lut_hierarchy_results.json'}")
    print(f"Core LUT ratio: {ratio:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
