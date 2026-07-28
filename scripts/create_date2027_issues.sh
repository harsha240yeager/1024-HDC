#!/usr/bin/env bash
# Create DATE 2027 strong-accept experiment issues from docs/.issue_bodies/date2027/
#
# Usage:
#   bash scripts/create_date2027_issues.sh
#   bash scripts/create_date2027_issues.sh --dry-run
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BODIES="$ROOT/docs/.issue_bodies/date2027"
REPO="${GITHUB_REPOSITORY:-harsha240yeager/1024-HDC}"

titles=(
  "[DATE27] Epic: Strong-accept experiment track (both papers)"
  "[DATE27][P0][Paper2] Stage-B iso-density ablation (S1)"
  "[DATE27][P0][Paper2] Stage-B ranking baselines on dense support"
  "[DATE27][P1][Paper2] Three-baseline iso-density hero figure"
  "[DATE27][P1][Paper2] Active-support mechanism (327 vs 209)"
  "[DATE27][P1][Paper2] Document encoder redundancy (level21_to_grid)"
  "[DATE27][P0][Both] Silicon random-mask seeds 1-9 on board"
  "[DATE27][P1][Both] Automation: run_silicon_random_seeds.sh"
  "[DATE27][P0][Paper1] Design narrow/gated popcount_am (H1)"
  "[DATE27][P0][Paper1] Implement + synth narrow/gated RTL"
  "[DATE27][P1][Paper1] Co-sim + golden verify (H1 RTL)"
  "[DATE27][P1][Paper1] Board eval: LUT/energy/latency vs keep (H1)"
  "[DATE27][P2][Paper1] Pareto figure + util compare script"
  "[DATE27][P2][Paper1] ARM NEON baseline (optional)"
  "[DATE27][P2][Paper2] Real per-feature encoder (optional)"
  "[DATE27][P2][Paper1] PL-rail energy (post-DATE)"
  "[DATE27][P1][Both] Integrate results into DATE manuscript"
  "[DATE27][P1][Both] Claim checker + regenerate figures"
  "[DATE27][P1] DATE 2027 submission checklist"
)

body_files=(
  "00_epic.md"
  "21_stage_b_isodensity.md"
  "22_stage_b_ranking.md"
  "23_three_baseline_figure.md"
  "24_active_support_mechanism.md"
  "25_encoder_redundancy.md"
  "26_silicon_seeds_1_9.md"
  "27_silicon_seed_script.md"
  "28_h1_design_narrow_gated.md"
  "29_h1_implement_synth.md"
  "30_h1_cosim_golden.md"
  "31_h1_board_eval.md"
  "32_h1_pareto_figure.md"
  "33_arm_neon_baseline.md"
  "34_real_feature_encoder.md"
  "35_pl_rail_energy.md"
  "36_integrate_manuscript.md"
  "37_claim_checker_figures.md"
  "38_date_submit_checklist.md"
)

labels=(
  "date-2027,P0-blocker"
  "date-2027,paper2-science,P0-blocker"
  "date-2027,paper2-science,P0-blocker"
  "date-2027,paper2-science,P1"
  "date-2027,paper2-science,P1"
  "date-2027,paper2-science,P1"
  "date-2027,paper1-hardware,paper2-science,P0-blocker"
  "date-2027,paper1-hardware,P1"
  "date-2027,paper1-hardware,P0-blocker"
  "date-2027,paper1-hardware,P0-blocker"
  "date-2027,paper1-hardware,P1"
  "date-2027,paper1-hardware,P1"
  "date-2027,paper1-hardware,P2"
  "date-2027,paper1-hardware,P2"
  "date-2027,paper2-science,P2"
  "date-2027,paper1-hardware,P2"
  "date-2027,P1"
  "date-2027,P1"
  "date-2027,P1"
)

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI required" >&2
  exit 1
fi

dry_run=0
[[ "${1:-}" == "--dry-run" ]] && dry_run=1

ensure_labels() {
  gh label create date-2027 --repo "$REPO" --color "1D76DB" \
    --description "DATE 2027 strong-accept experiment track" 2>/dev/null || true
  gh label create paper1-hardware --repo "$REPO" --color "5319E7" \
    --description "Split Paper 1 — Zynq accelerator" 2>/dev/null || true
  gh label create paper2-science --repo "$REPO" --color "0E8A16" \
    --description "Split Paper 2 — iso-density science" 2>/dev/null || true
  gh label create P1 --repo "$REPO" --color "FBCA04" \
    --description "High priority — before DATE submit" 2>/dev/null || true
  gh label create P2 --repo "$REPO" --color "C5DEF5" \
    --description "Optional / post-DATE" 2>/dev/null || true
}

ensure_labels

created=()
for i in "${!titles[@]}"; do
  title="${titles[$i]}"
  body_file="$BODIES/${body_files[$i]}"
  label="${labels[$i]}"

  if [[ $dry_run -eq 1 ]]; then
    echo "${body_files[$i]}  $title  [$label]"
    continue
  fi

  if gh issue list --repo "$REPO" --search "$title in:title" --state all \
    --json number --jq '.[0].number' 2>/dev/null | grep -qE '^[0-9]+$'; then
    num=$(gh issue list --repo "$REPO" --search "$title in:title" --state all \
      --json number --jq '.[0].number')
    echo "SKIP (exists #$num): $title"
    created+=("$num")
    continue
  fi

  num=$(gh issue create --repo "$REPO" --title "$title" --label "$label" \
    --body-file "$body_file" | grep -oE '[0-9]+$')
  echo "Created #$num: $title"
  created+=("$num")
done

if [[ $dry_run -eq 1 ]]; then
  exit 0
fi

epic_num="${created[0]}"
if [[ -n "$epic_num" ]] && [[ ${#created[@]} -gt 1 ]]; then
  {
    echo "## Child issues (priority order)"
    echo
    for j in "${!titles[@]}"; do
      [[ $j -eq 0 ]] && continue
      echo "$((j)). #${created[$j]} — ${titles[$j]}"
    done
    echo
    echo "Legacy: #3 random-mask FPGA work superseded by #${created[6]}."
  } > "$ROOT/docs/.issue_bodies/date2027/_epic_children.md"

  gh issue edit "$epic_num" --repo "$REPO" \
    --body-file "$BODIES/00_epic.md" 2>/dev/null || true
  gh issue comment "$epic_num" --repo "$REPO" \
    --body-file "$ROOT/docs/.issue_bodies/date2027/_epic_children.md"

  gh issue comment 3 --repo "$REPO" --body \
    "FPGA random-mask seeds moved to DATE27 track: see #${created[6]} (and epic #${epic_num}). Python items in this issue remain done." \
    2>/dev/null || true
fi

echo "Done. Epic: #${epic_num:-?}"
