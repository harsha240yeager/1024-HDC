#!/usr/bin/env bash
# Full workflow: energy (pause for review) — run run_after_energy_review.sh separately.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec > >(tee -a "$ROOT/results/phase3/full_workflow.log") 2>&1
bash "$ROOT/scripts/run_energy_only.sh"
