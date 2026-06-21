# Prepare golden-vector header for Zynq bare-metal build (run from repo root).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VecDir = Join-Path $Root "python_ref\vectors\cosim_core"
$OutH   = Join-Path $Root "sw\golden_vectors.h"

if (-not (Test-Path (Join-Path $VecDir "core_expect.hex"))) {
    Write-Host "Generating core vectors (seed 42, 200 cases)..."
    Set-Location (Join-Path $Root "python_ref")
    python generate_vectors.py --core --out-dir vectors/cosim_core --count 200 --seed 42
    Set-Location $Root
}

Write-Host "Exporting C header..."
python (Join-Path $Root "python_ref\tools\export_golden_c.py") $VecDir $OutH

Write-Host ""
Write-Host "Ready. Vitis application sources:"
Write-Host "  sw/hdc_core_golden_test.c  (200-case golden test)"
Write-Host "  sw/hdc_core_bench.c       (Phase 1 latency bench)"
Write-Host "  sw/hdc_core_regs.c"
Write-Host "  sw/golden_vectors.h"
Write-Host ""
Write-Host "Add sw/ to include path. UART 115200 - expect PASS: 200/200 golden cases"
