#!/usr/bin/env bash
# Copy manuscript figures from 1024-HDC to Research-paper (issue #37).
set -euo pipefail
HDC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAPER_ROOT="${RESEARCH_PAPER_ROOT:-$HDC_ROOT/../Research-paper}"
FIG="$HDC_ROOT/results/figures"
DEST="$PAPER_ROOT/figures"

if [[ ! -d "$PAPER_ROOT" ]]; then
  echo "missing Research-paper at $PAPER_ROOT" >&2
  exit 1
fi
mkdir -p "$DEST"

copy() {
  local f="$1"
  if [[ -f "$FIG/$f" ]]; then
    cp -a "$FIG/$f" "$DEST/$f"
    echo "  $f"
  else
    echo "  skip (missing) $f" >&2
  fi
}

echo "Syncing PDF figures to $DEST"
copy narrow_vs_baseline_pareto.pdf
copy twist1_three_baselines_keep0125.pdf
copy twist2_cross_subject_36.pdf
copy hookA_pareto_measured.pdf
copy hookA_anchor_energy.pdf
copy baselines_bar.pdf
copy fisher_heatmap.pdf
copy twist1_informed_vs_random_keep0125.pdf
echo "Done."
