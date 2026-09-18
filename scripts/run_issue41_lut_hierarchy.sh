#!/usr/bin/env bash
# Issue #41 — parse Vivado reports into LUT/cycle breakdown (no new P&R).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/build_lut_hierarchy_issue41.py "$@"
