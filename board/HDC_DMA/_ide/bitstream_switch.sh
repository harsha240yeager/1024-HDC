#!/usr/bin/env bash
# Swap active design_1_wrapper.bit between baseline integrated and narrow (issue #31).
# Source from other board scripts; do not run standalone unless testing.
set -euo pipefail

_hdc_bs_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

hdc_bitstream_dir() {
  echo "$(_hdc_bs_root)/app/_ide/bitstream"
}

hdc_activate_narrow_bitstream() {
  local dir
  dir="$(hdc_bitstream_dir)"
  local active="$dir/design_1_wrapper.bit"
  local narrow="$dir/design_1_wrapper.narrow.bit"
  local baseline="$dir/design_1_wrapper.baseline.bit"
  if [[ ! -f "$narrow" ]]; then
    echo "ERROR: missing narrow bitstream $narrow" >&2
    return 1
  fi
  if [[ -f "$active" && ! -f "$baseline" ]]; then
    cp -f "$active" "$baseline"
    echo "Saved active bitstream -> design_1_wrapper.baseline.bit"
  fi
  cp -f "$narrow" "$active"
  echo "Active PL bitstream: narrow ($(md5sum "$active" | awk '{print $1}'))"
}

hdc_restore_baseline_bitstream() {
  local dir
  dir="$(hdc_bitstream_dir)"
  local active="$dir/design_1_wrapper.bit"
  local baseline="$dir/design_1_wrapper.baseline.bit"
  if [[ ! -f "$baseline" ]]; then
    echo "WARNING: no design_1_wrapper.baseline.bit — leaving active bitstream unchanged" >&2
    return 0
  fi
  cp -f "$baseline" "$active"
  echo "Restored baseline PL bitstream ($(md5sum "$active" | awk '{print $1}'))"
}
