#!/usr/bin/env bash
# One-command reproduction of the Python portions of the DATE manuscript.
#
#   bash scripts/reproduce_paper.sh --verify-only   # check committed numbers (seconds)
#   bash scripts/reproduce_paper.sh --tier smoke    # ~30 min sanity rerun
#   bash scripts/reproduce_paper.sh --tier core     # ~21 h, every S1-S5 claim
#   bash scripts/reproduce_paper.sh --tier full     # ~3 days, adds Hook A + 36 subjects
#
# Runtimes below are measured wall-clock from the committed runs (elapsed_s in
# each results JSON) on one 30-thread workstation, not guesses.
#
# Reruns write to results/repro/<tier>/ so committed artifacts are never
# overwritten; compare the two trees before updating the paper. Board replay,
# INA219 energy, and Vivado synthesis need a ZedBoard and are documented in
# docs/REPRODUCIBILITY.md instead.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TIER="core"
OUT_ROOT=""
VERIFY_ONLY=0
DRY_RUN=0
ONLY=""
SKIP_VERIFY=0

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --tier {smoke,core,full}  How much to rerun (default: core)
  --only STAGE              Run a single stage by name (see --list)
  --list                    Print the stage table for the selected tier and exit
  --out-root DIR            Output root (default: results/repro/<tier>)
  --verify-only             Skip reruns; only check committed numbers
  --skip-verify             Run stages but skip the final claim check
  --dry-run                 Print what would run without running it
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier) TIER="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --out-root) OUT_ROOT="$2"; shift 2 ;;
    --list) LIST_ONLY=1; shift ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    --skip-verify) SKIP_VERIFY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done
LIST_ONLY="${LIST_ONLY:-0}"

case "$TIER" in
  smoke|core|full) ;;
  *) echo "--tier must be smoke, core, or full" >&2; exit 2 ;;
esac

OUT_ROOT="${OUT_ROOT:-results/repro/$TIER}"
LOG_DIR="$OUT_ROOT/logs"

# Probe by executing, not by `command -v`: Windows ships a python3 alias stub
# that resolves but cannot run.
PY=""
for candidate in python3 python py; do
  if "$candidate" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
[[ -n "$PY" ]] || { echo "no working python3/python interpreter on PATH" >&2; exit 1; }

EMG_CFG="python_ref/config/emg_baseline_v2.json"
DATASET_5="python_ref/HDC-EMG/dataset.mat"
DATASET_36="python_ref/HDC-EMG/dataset_36.mat"

# --------------------------------------------------------------------------
# Stage table: name | tiers | dataset | estimated runtime | command
# --------------------------------------------------------------------------
stages() {
  cat <<EOF
gate|smoke core full|none|1 min|bash scripts/run_hdc2_gate.sh
split_audit|smoke core full|5|2 min|$PY scripts/audit_split_leakage.py --config $EMG_CFG
baseline|core full|5|40 min|$PY python_ref/run_emg_baseline.py --config config/emg_baseline_v2.json
twist1_quick|smoke|5|15 min|$PY python_ref/run_twist1_sweep.py --quick --emg-config $EMG_CFG --keep 0.125 --out-dir $OUT_ROOT/twist1_quick
twist1_30seed|core full|5|2.6 h|$PY python_ref/run_twist1_sweep.py --emg-config $EMG_CFG --keep 0.125 --random-seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 --out-dir $OUT_ROOT/twist1_keep0125_30seed
twist1_stats|core full|none|1 min|$PY python_ref/tools/subject_level_stats.py --results $OUT_ROOT/twist1_keep0125_30seed/twist1_results.json --out-dir $OUT_ROOT/twist1_keep0125_30seed
ranking_quick|smoke|5|10 min|$PY python_ref/run_ranking_baselines.py --quick --emg-config $EMG_CFG --out-dir $OUT_ROOT/ranking_baselines_quick
ranking|core full|5|23 min|$PY python_ref/run_ranking_baselines.py --emg-config $EMG_CFG --out-dir $OUT_ROOT/ranking_baselines
active_bits|core full|5|4.3 h|$PY python_ref/run_active_bit_ablation.py --emg-config $EMG_CFG --out-dir $OUT_ROOT/active_bits
seed_sensitivity|core full|5|9.9 h|$PY python_ref/run_seed_sensitivity.py --emg-config $EMG_CFG --out-dir $OUT_ROOT/seed_sensitivity
encoder_ablation|core full|5|47 min|$PY python_ref/run_encoder_ablation.py --emg-config $EMG_CFG --out-dir $OUT_ROOT/encoder_ablation
twist2_pilot|core full|5|2.4 h|$PY python_ref/run_twist2_sweep.py --emg-config $EMG_CFG --out-dir $OUT_ROOT/twist2_keep0125
hook_a|full|5|35.4 h|$PY python_ref/run_hook_a_sweep.py --emg-config $EMG_CFG --out-dir $OUT_ROOT/hook_a
twist2_36_grid|full|36|8.6 h|bash scripts/run_twist2_36_v2_keep_grid.sh --out-root $OUT_ROOT/twist2_36_v2
figures|core full|none|2 min|$PY python_ref/plot_results.py --paper
EOF
}

selected_stages() {
  stages | while IFS='|' read -r name tiers data eta cmd; do
    [[ " $tiers " == *" $TIER "* ]] || continue
    [[ -z "$ONLY" || "$ONLY" == "$name" ]] || continue
    printf '%s|%s|%s|%s|%s\n' "$name" "$tiers" "$data" "$eta" "$cmd"
  done
}

print_list() {
  printf '%-18s %-8s %-10s %s\n' "STAGE" "DATASET" "ETA" "COMMAND"
  printf '%s\n' "--------------------------------------------------------------------------------"
  selected_stages | while IFS='|' read -r name tiers data eta cmd; do
    printf '%-18s %-8s %-10s %s\n' "$name" "$data" "$eta" "$cmd"
  done
}

require_dataset() {
  local which="$1" stage="$2"
  case "$which" in
    5)
      [[ -f "$DATASET_5" ]] && return 0
      echo "SKIP $stage — missing $DATASET_5"
      echo "     clone https://github.com/abbas-rahimi/HDC-EMG into python_ref/HDC-EMG (GPLv3, not redistributed here)"
      return 1 ;;
    36)
      [[ -f "$DATASET_36" ]] && return 0
      echo "SKIP $stage — missing $DATASET_36"
      echo "     build it with scripts/build_uci_emg_dataset.py (see docs/TWIST2_36_REPRO.md)"
      return 1 ;;
    *) return 0 ;;
  esac
}

verify() {
  echo
  echo "=== Claim check against committed artifacts ==="
  "$PY" scripts/check_paper_numbers.py --json "$OUT_ROOT/claim_check.json"
}

# --------------------------------------------------------------------------
if [[ "$LIST_ONLY" == 1 ]]; then
  print_list
  exit 0
fi

if [[ "$VERIFY_ONLY" == 1 ]]; then
  mkdir -p "$OUT_ROOT"
  verify
  exit $?
fi

mkdir -p "$LOG_DIR"
echo "tier=$TIER  out=$OUT_ROOT  python=$($PY --version 2>&1)"
echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo 'not a git checkout')"
echo
print_list
echo

RAN=0
SKIPPED=0
FAILED=0
START_ALL=$(date +%s)

while IFS='|' read -r name tiers data eta cmd; do
  if ! require_dataset "$data" "$name"; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  echo "--- $name (eta $eta) ---"
  if [[ "$DRY_RUN" == 1 ]]; then
    echo "    $cmd"
    continue
  fi
  START=$(date +%s)
  if bash -c "$cmd" >"$LOG_DIR/$name.log" 2>&1; then
    echo "    OK in $(( ($(date +%s) - START) / 60 )) min — $LOG_DIR/$name.log"
    RAN=$((RAN + 1))
  else
    echo "    FAILED after $(( ($(date +%s) - START) / 60 )) min — see $LOG_DIR/$name.log"
    tail -n 15 "$LOG_DIR/$name.log" | sed 's/^/      /'
    FAILED=$((FAILED + 1))
  fi
done < <(selected_stages)

echo
echo "stages: $RAN ran, $SKIPPED skipped, $FAILED failed in $(( ($(date +%s) - START_ALL) / 60 )) min"

if [[ "$SKIP_VERIFY" != 1 && "$DRY_RUN" != 1 ]]; then
  verify || FAILED=$((FAILED + 1))
fi

[[ "$FAILED" -eq 0 ]]
