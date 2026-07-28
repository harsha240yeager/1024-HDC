# Create DATE 2027 strong-accept experiment issues (Windows / PowerShell)
# Usage: powershell -File scripts/create_date2027_issues.ps1
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$REPO = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { "harsha240yeager/1024-HDC" }
$BODIES = Join-Path $ROOT "docs\.issue_bodies\date2027"

$titles = @(
  "[DATE27] Epic: Strong-accept experiment track (both papers)",
  "[DATE27][P0][Paper2] Stage-B iso-density ablation (S1)",
  "[DATE27][P0][Paper2] Stage-B ranking baselines on dense support",
  "[DATE27][P1][Paper2] Three-baseline iso-density hero figure",
  "[DATE27][P1][Paper2] Active-support mechanism (327 vs 209)",
  "[DATE27][P1][Paper2] Document encoder redundancy (level21_to_grid)",
  "[DATE27][P0][Both] Silicon random-mask seeds 1-9 on board",
  "[DATE27][P1][Both] Automation: run_silicon_random_seeds.sh",
  "[DATE27][P0][Paper1] Design narrow/gated popcount_am (H1)",
  "[DATE27][P0][Paper1] Implement + synth narrow/gated RTL",
  "[DATE27][P1][Paper1] Co-sim + golden verify (H1 RTL)",
  "[DATE27][P1][Paper1] Board eval: LUT/energy/latency vs keep (H1)",
  "[DATE27][P2][Paper1] Pareto figure + util compare script",
  "[DATE27][P2][Paper1] ARM NEON baseline (optional)",
  "[DATE27][P2][Paper2] Real per-feature encoder (optional)",
  "[DATE27][P2][Paper1] PL-rail energy (post-DATE)",
  "[DATE27][P1][Both] Integrate results into DATE manuscript",
  "[DATE27][P1][Both] Claim checker + regenerate figures",
  "[DATE27][P1] DATE 2027 submission checklist"
)

$bodyFiles = @(
  "00_epic.md","21_stage_b_isodensity.md","22_stage_b_ranking.md","23_three_baseline_figure.md",
  "24_active_support_mechanism.md","25_encoder_redundancy.md","26_silicon_seeds_1_9.md",
  "27_silicon_seed_script.md","28_h1_design_narrow_gated.md","29_h1_implement_synth.md",
  "30_h1_cosim_golden.md","31_h1_board_eval.md","32_h1_pareto_figure.md","33_arm_neon_baseline.md",
  "34_real_feature_encoder.md","35_pl_rail_energy.md","36_integrate_manuscript.md",
  "37_claim_checker_figures.md","38_date_submit_checklist.md"
)

$labels = @(
  "date-2027,P0-blocker","date-2027,paper2-science,P0-blocker","date-2027,paper2-science,P0-blocker",
  "date-2027,paper2-science,P1","date-2027,paper2-science,P1","date-2027,paper2-science,P1",
  "date-2027,paper1-hardware,paper2-science,P0-blocker","date-2027,paper1-hardware,P1",
  "date-2027,paper1-hardware,P0-blocker","date-2027,paper1-hardware,P0-blocker",
  "date-2027,paper1-hardware,P1","date-2027,paper1-hardware,P1","date-2027,paper1-hardware,P2",
  "date-2027,paper1-hardware,P2","date-2027,paper2-science,P2","date-2027,paper1-hardware,P2",
  "date-2027,P1","date-2027,P1","date-2027,P1"
)

foreach ($l in @("date-2027","paper1-hardware","paper2-science","P1","P2")) {
  gh label create $l --repo $REPO --force 2>$null
}

$created = @()
for ($i = 0; $i -lt $titles.Count; $i++) {
  $title = $titles[$i]
  $body = Join-Path $BODIES $bodyFiles[$i]
  $label = $labels[$i]
  $existing = gh issue list --repo $REPO --search "$title in:title" --state all --json number --jq ".[0].number" 2>$null
  if ($existing -match '^\d+$') {
    Write-Host "SKIP (exists #$existing): $title"
    $created += [int]$existing
    continue
  }
  $url = gh issue create --repo $REPO --title $title --label $label --body-file $body
  $num = [regex]::Match($url, '\d+$').Value
  Write-Host "Created #$num : $title"
  $created += [int]$num
}

Write-Host "Done. Epic: #$($created[0])"
