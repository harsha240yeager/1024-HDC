#!/usr/bin/env bash
# Parse OOC util reports into results/dsweep/narrow_vs_baseline_util.csv
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DS="$ROOT/results/dsweep"
OUT="$DS/narrow_vs_baseline_util.csv"

scrape() {
  local file="$1" label="$2"
  awk -F'|' -v lbl="$label" '
    index($0, lbl) { gsub(/ /,"",$3); print $3; exit }
  ' "$file"
}

wns_from() {
  local file="$1"
  grep -E 'WNS\(ns\)' "$file" 2>/dev/null | tail -1 | awk -F'|' '{gsub(/ /,"",$2); print $2}' || echo n/a
}

add_row() {
  local variant="$1" top="$2" k="$3" scope="$4" rpt="$5"
  local f="$DS/$rpt"
  if [[ ! -f "$f" ]]; then
    echo "missing $f" >&2
    return 1
  fi
  local lut ff wns fmax
  lut=$(scrape "$f" "Slice LUTs")
  ff=$(scrape "$f" "Slice Registers")
  wns=$(wns_from "$f")
  if [[ "$wns" != "n/a" && "$wns" =~ ^-?[0-9] ]]; then
    fmax=$(python3 -c "print(f'{1000/(10.0-float(\"$wns\")):.1f}')")
  else
    fmax=n/a
  fi
  echo "$variant,$top,$k,$scope,$lut,$ff,$wns,$fmax,$rpt"
}

{
  echo "variant,top,k_bits,scope,lut,ff,wns_ns,fmax_mhz,report"
  add_row baseline hdc_core_top 1024 ooc_core synth_baseline_core.txt
  add_row narrow hdc_core_top_narrow 128 ooc_core synth_narrow_core.txt
  if [[ -f "$DS/synth_baseline_stream.txt" ]]; then
    add_row baseline hdc_stream_wrapper 1024 ooc_stream synth_baseline_stream.txt
  fi
  if [[ -f "$DS/synth_narrow_stream.txt" ]]; then
    add_row narrow hdc_stream_wrapper_narrow 128 ooc_stream synth_narrow_stream.txt
  fi
  if [[ -f "$DS/synth_baseline_bd.txt" ]]; then
    add_row baseline hdc_stream_system_bd_wrapper 1024 ooc_integrated synth_baseline_bd.txt
  fi
  if [[ -f "$DS/synth_narrow_bd.txt" ]]; then
    add_row narrow hdc_stream_system_bd_wrapper_narrow 128 ooc_integrated synth_narrow_bd.txt
  fi
} > "$OUT"

echo "Wrote $OUT"
column -t -s, "$OUT" 2>/dev/null || cat "$OUT"
