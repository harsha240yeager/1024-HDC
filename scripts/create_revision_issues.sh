#!/usr/bin/env bash
# Create GitHub issues #1–#11 from docs/.issue_bodies/ (requires gh CLI + auth).
#
# Usage:
#   bash scripts/create_revision_issues.sh          # create missing issues
#   bash scripts/create_revision_issues.sh --dry-run  # print titles only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BODIES="$ROOT/docs/.issue_bodies"
REPO="${GITHUB_REPOSITORY:-harsha240yeager/1024-HDC}"

titles=(
  "Phase 1: Protocol HDC-2 disjoint split + full rerun (BLOCKER)"
  "Phase 2: Cross-subject transfer under accuracy stress"
  "Phase 3: Expand random-mask baseline + subject-level statistics"
  "Phase 4: Item-memory seed sensitivity"
  "Phase 5: Active-bit ablation (257 positions) + ranking baselines"
  "Phase 6: Encoder gap 74% vs 90%"
  "Phase 7: Align claims with what pruning changes"
  "Phase 8: Energy measurement methodology"
  "Phase 9: Ranking baselines (variance, MI, …)"
  "Phase 10: Fix internal inconsistencies (figures, metrics)"
  "Phase 11: Reproducibility artifact (Zenodo / tagged release)"
)

labels=(
  "date-revision,P0-blocker"
  "date-revision,blocked"
  "date-revision,blocked"
  "date-revision,blocked"
  "date-revision,blocked"
  "date-revision"
  "date-revision"
  "date-revision"
  "date-revision,blocked"
  "date-revision"
  "date-revision"
)

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not installed. Issue bodies are in docs/.issue_bodies/" >&2
  echo "Create issues manually or: sudo apt install gh && gh auth login" >&2
  exit 1
fi

dry_run=0
[[ "${1:-}" == "--dry-run" ]] && dry_run=1

for i in $(seq 1 11); do
  id=$(printf "%02d" "$i")
  body_file="$BODIES/${id}_"*.md
  body_file=( $body_file )
  title="${titles[$((i - 1))]}"
  label="${labels[$((i - 1))]}"

  if [[ $dry_run -eq 1 ]]; then
    echo "#$i  $title  [$label]"
    continue
  fi

  if gh issue list --repo "$REPO" --search "$title" --json number --jq '.[0].number' 2>/dev/null | grep -q .; then
    echo "SKIP #$i (similar title exists): $title"
    continue
  fi

  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --label "$label" \
    --body-file "${body_file[0]}"
  echo "Created #$i: $title"
done

echo "Done. Track progress in docs/DATE_REVISION_PLAN.md status board."
