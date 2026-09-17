#!/usr/bin/env bash
# Issue #31 — narrow board eval: optional live bench/energy + summary generation.
#
# Usage:
#   bash scripts/run_issue31_narrow_board_eval.sh           # summary only (committed artifacts)
#   bash scripts/run_issue31_narrow_board_eval.sh --bench   # refresh latency bench
#   bash scripts/run_issue31_narrow_board_eval.sh --energy  # INA219 x3 (Pi + ZedBoard)
#   bash scripts/run_issue31_narrow_board_eval.sh --all     # bench + energy + summary
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-summary}"

run_summary() {
  python3 "$ROOT/scripts/gen_narrow_board_eval_summary.py"
}

case "$MODE" in
  summary|--summary)
    run_summary
    ;;
  --bench)
    bash "$ROOT/board/HDC_DMA/run_narrow_phase3_bench.sh"
    run_summary
    ;;
  --energy)
    bash "$ROOT/scripts/run_narrow_energy_campaign.sh"
    run_summary
    ;;
  --all)
    bash "$ROOT/board/HDC_DMA/run_narrow_phase3_bench.sh"
    bash "$ROOT/scripts/run_narrow_energy_campaign.sh"
    run_summary
    ;;
  *)
    echo "Usage: $0 [summary|--bench|--energy|--all]" >&2
    exit 1
    ;;
esac
