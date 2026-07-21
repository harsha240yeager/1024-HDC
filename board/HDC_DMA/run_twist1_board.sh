#!/usr/bin/env bash
# Twist 1 on silicon — Fisher informed vs random mask @ iso-density (keep=0.125 / 128 bits).
#
# Informed path reuses anchor C (pooled Fisher @ keep=0.125) unless --rerun-informed.
# Random path patches a uniform random 128-bit mask, rebuilds EMG ELF, runs JTAG replay.
#
# Usage (from repo root):
#   bash board/HDC_DMA/run_twist1_board.sh
#   bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0
#   bash board/HDC_DMA/run_twist1_board.sh --random-seeds 0,1,2 --rerun-informed
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
OUT_BASE="$REPO/results/phase3/twist1_silicon"
KEEP="0.125"
RANDOM_SEEDS="0"
RERUN_INFORMED=0
SKIP_PATCH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep) KEEP="$2"; shift 2 ;;
    --random-seeds) RANDOM_SEEDS="$2"; shift 2 ;;
    --rerun-informed) RERUN_INFORMED=1; shift ;;
    --skip-patch) SKIP_PATCH=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

IFS=',' read -ra SEED_ARR <<< "$RANDOM_SEEDS"

anchor_id_for_keep() {
  case "$1" in
    1.0|1) echo "A" ;;
    0.5) echo "B" ;;
    0.125) echo "C" ;;
    *) echo "?" ;;
  esac
}

ANCHOR_ID="$(anchor_id_for_keep "$KEEP")"
INFORMED_DIR="$OUT_BASE/informed_anchor_${ANCHOR_ID}"
mkdir -p "$OUT_BASE"

# Fresh hw_server avoids stale JTAG (DAP 0x30000021 / missing APU).
# shellcheck source=/dev/null
source "$ROOT/_ide/common.sh"
hdc_stop_conflicting_sessions || true
hdc_stop_hw_server || true
sleep 2

echo "=== Twist 1 silicon @ keep=${KEEP} (anchor ${ANCHOR_ID}) ==="

# --- Informed (anchor C @ 0.125) ---
if [[ "$RERUN_INFORMED" -eq 1 ]]; then
  mkdir -p "$INFORMED_DIR"
  echo "--- Informed: patch + board replay ---"
  if [[ "$SKIP_PATCH" -eq 0 ]]; then
    python3 "$REPO/scripts/patch_emg_anchor.py" \
      --anchor "$ANCHOR_ID" --keep-ratio "$KEEP" \
      --mask-mode informed --label twist1_informed
  fi
  export HDC_EMG_RESULTS="$INFORMED_DIR/board_emg_replay.txt"
  export HDC_LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_twist1_informed}"
  bash "$ROOT/run_anchor_replay.sh" "$ANCHOR_ID"
else
  echo "--- Informed: reuse anchor ${ANCHOR_ID} board result ---"
  SRC="$REPO/results/protocol_v2/anchors/anchor_${ANCHOR_ID}/board_emg_replay.txt"
  if [[ ! -f "$SRC" ]]; then
    echo "Missing $SRC — run: bash board/HDC_DMA/run_anchor_replay.sh ${ANCHOR_ID}" >&2
    exit 1
  fi
  mkdir -p "$INFORMED_DIR"
  cp -f "$SRC" "$INFORMED_DIR/board_emg_replay.txt"
  echo "Copied $SRC -> $INFORMED_DIR/"
fi

grep -E "accuracy=|Export ref:" "$INFORMED_DIR/board_emg_replay.txt" | head -3 || true

# --- Random seeds ---
for seed in "${SEED_ARR[@]}"; do
  seed="$(echo "$seed" | tr -d ' ')"
  [[ -z "$seed" ]] && continue
  RDIR="$OUT_BASE/random_seed_${seed}"
  mkdir -p "$RDIR"
  echo ""
  echo "--- Random seed=${seed}: patch + board replay ---"
  if [[ "$SKIP_PATCH" -eq 0 ]]; then
    python3 "$REPO/scripts/patch_emg_anchor.py" \
      --anchor "$ANCHOR_ID" --keep-ratio "$KEEP" \
      --mask-mode random --random-seed "$seed" \
      --label "twist1_random_s${seed}"
  fi
  export HDC_EMG_RESULTS="$RDIR/board_emg_replay.txt"
  export HDC_EMG_RESULTS_DIR="$RDIR"
  export HDC_LOG_DIR="/tmp/hdc_twist1_random_${seed}"
  export HDC_ANCHOR_SKIP_PATCH=1
  bash "$ROOT/run_anchor_replay.sh" "$ANCHOR_ID"
  unset HDC_ANCHOR_SKIP_PATCH
  grep -E "accuracy=|Export ref:" "$RDIR/board_emg_replay.txt" | head -3 || true
done

# Summary
python3 - <<'PY' "$OUT_BASE" "$INFORMED_DIR"
import re, sys
from pathlib import Path

out_base = Path(sys.argv[1])
informed_dir = Path(sys.argv[2])

def parse_acc(path: Path):
    text = path.read_text()
    m = re.search(r"accuracy=([\d.]+)%", text)
    return float(m.group(1)) if m else None

inf = parse_acc(informed_dir / "board_emg_replay.txt")
lines = [
    "# Twist 1 — silicon informed vs random @ keep=0.125",
    "",
    f"| Condition | Board accuracy |",
    f"|-----------|----------------|",
    f"| Fisher informed (anchor C) | **{inf:.2f}%** |" if inf else "| Fisher informed | — |",
]
gaps = []
for d in sorted(out_base.glob("random_seed_*")):
    acc = parse_acc(d / "board_emg_replay.txt")
    if acc is None:
        continue
    seed = d.name.replace("random_seed_", "")
    gap = (inf - acc) if inf is not None else 0.0
    gaps.append(gap)
    lines.append(f"| Random seed {seed} | **{acc:.2f}%** |")
if inf is not None and gaps:
    lines.extend([
        "",
        f"**Gap (informed − random):** {sum(gaps)/len(gaps):+.2f} pp (mean over {len(gaps)} seed(s))",
    ])
(out_base / "README.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
PY

echo ""
echo "Twist 1 silicon complete -> $OUT_BASE/README.md"
