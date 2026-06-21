#!/usr/bin/env bash
# JTAG helpers for HDC_DMA board scripts (self-contained in this repo).
set -euo pipefail

HDC_DMA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HDC_DMA_ROOT/../.." && pwd)"
HDC_VIVADO_ROOT="${HDC_VIVADO_ROOT:-}"
HDC_PORT="${HDC_PORT:-/dev/ttyUSB0}"
HDC_BAUD="${HDC_BAUD:-115200}"
HDC_HW_SERVER_URL="tcp:127.0.0.1:3121"
HDC_LOG_DIR="${HDC_LOG_DIR:-/tmp/hdc_dma}"

hdc_source_tools() {
  local had_nounset=0
  case $- in
    *u*) had_nounset=1; set +u ;;
  esac
  source /cad/Xilinx/Vitis/2024.2/settings64.sh
  source /cad/Xilinx/Vivado/2024.2/settings64.sh
  if [[ "$had_nounset" -eq 1 ]]; then
    set -u
  fi
}

hdc_xsdb() {
  hdc_source_tools
  TERM="${HDC_XSDB_TERM:-dumb}" /cad/Xilinx/Vitis/2024.2/bin/loader -exec rdi_xsdb "$@"
}

hdc_hw_server_pids() {
  pgrep -f '/unwrapped/lnx64.o/hw_server -s tcp:127.0.0.1:3121' || true
}

hdc_stop_hw_server() {
  local pid
  for pid in $(hdc_hw_server_pids); do
    kill "$pid" 2>/dev/null || true
  done
  pkill -f 'hw_server.*3121' 2>/dev/null || true
  sleep 2
}

hdc_start_hw_server() {
  hdc_source_tools
  hdc_stop_hw_server
  hw_server -s "$HDC_HW_SERVER_URL" >/tmp/hdc_hw_server.log 2>&1 &
  local i
  for i in $(seq 1 20); do
    if hdc_hw_server_pids | grep -q .; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: hw_server failed to start. See /tmp/hdc_hw_server.log" >&2
  return 1
}

hdc_ensure_hw_server() {
  if hdc_hw_server_pids | grep -q .; then
    return 0
  fi
  hdc_start_hw_server
}

hdc_stop_conflicting_sessions() {
  local stopped=0

  if pgrep -f 'minicom.*ttyUSB0' >/dev/null; then
    echo "ERROR: Close minicom first (Ctrl+A, X, Y)." >&2
    return 1
  fi

  if pgrep -f 'rdi_xsct.*temp_xsdb_launch|unwrapped/lnx64.o/rdi_xsct' >/dev/null; then
    echo "Stopping stale Vitis debug session..."
    pkill -f 'temp_xsdb_launch' 2>/dev/null || true
    pkill -f 'unwrapped/lnx64.o/rdi_xsct' 2>/dev/null || true
    stopped=1
  fi

  if pgrep -f 'rdi_xsdb.*temp_xsct_launch' >/dev/null; then
    echo "Stopping stale xsdb launch session..."
    pkill -f 'temp_xsct_launch' 2>/dev/null || true
    stopped=1
  fi

  if [[ "$stopped" -eq 1 ]]; then
    sleep 2
  fi
}

hdc_wait_for_digilent_usb() {
  local max_wait="${1:-30}"
  local i

  echo "=== Waiting for Digilent USB cable ==="
  for i in $(seq 1 "$max_wait"); do
    if lsusb | grep -q '0403:6014' && [[ -e /dev/ttyUSB0 ]]; then
      echo "Digilent cable detected on /dev/ttyUSB0"
      return 0
    fi
    sleep 1
  done

  echo "ERROR: Digilent cable not detected after ${max_wait}s." >&2
  echo "Check: board powered on, JP7 in JTAG, PROG-UART USB connected." >&2
  return 1
}
