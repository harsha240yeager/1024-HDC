# Issue #26 — run on ZedBoard lab machine (Git Bash or Linux)
#
#   bash scripts/run_silicon_random_seeds.sh --board --seeds 1-9 --resume
#
# Windows (Git Bash): ensure python3 works — use repo wrapper:
#   powershell -File scripts/run_silicon_random_seeds.ps1 -Board -Seeds 1-9

param(
    [string]$Seeds = "0-9",
    [switch]$Board,
    [switch]$Resume,
    [switch]$Quick
)

$ROOT = Split-Path -Parent $PSScriptRoot
$OUT = Join-Path $ROOT "results\protocol_v2\twist1_silicon"
$PY = $null
foreach ($c in @("python", "python3", "py")) {
    if (& $c -c "import sys; sys.exit(0)" 2>$null) { $PY = $c; break }
}
if (-not $PY) { throw "No Python found" }

$predArgs = @("--from-dataset", "--out-dir", $OUT)
if ($Quick) { $predArgs += "--max-windows", "5000" }

# Expand seed range
$seedList = @()
if ($Seeds -match "^(\d+)-(\d+)$") {
    for ($i = [int]$Matches[1]; $i -le [int]$Matches[2]; $i++) { $seedList += $i }
} else {
    $seedList = $Seeds.Split(",") | ForEach-Object { [int]$_.Trim() }
}
$predArgs += "--seeds"
$predArgs += $seedList

Write-Host "=== Python prediction ==="
& $PY (Join-Path $ROOT "python_ref\predict_twist1_silicon_seeds.py") @predArgs
if (-not $Board) { exit $LASTEXITCODE }

$bash = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path $bash)) { throw "Git Bash required for board replay" }

$boardSeeds = ($seedList | Where-Object { $_ -ge 1 }) -join ","
if (-not $boardSeeds) { Write-Host "No seeds >= 1 for board"; exit 0 }

$resumeFlag = if ($Resume) { "--resume" } else { "" }
$env:PATH = "$(Split-Path (Get-Command $PY).Source -Parent);$env:PATH"
& $bash -c "cd '$($ROOT -replace '\\','/')' && export PATH=`"'$(Split-Path (Get-Command $PY).Source -Parent | ForEach-Object { $_ -replace '\\','/' })':`$PATH`" && bash scripts/run_silicon_random_seeds.sh --board --seeds $boardSeeds $resumeFlag"
