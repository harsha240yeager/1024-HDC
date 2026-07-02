#!/usr/bin/env bash
# Resume: energy only — stops for review (no auto push / anchors).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec > >(tee -a "$ROOT/results/phase3/full_workflow_resume.log") 2>&1
bash "$ROOT/scripts/run_energy_only.sh"
