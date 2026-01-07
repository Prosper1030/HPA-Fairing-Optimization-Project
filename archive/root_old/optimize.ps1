# Quick launcher for main optimization (PowerShell version)
# Just run: .\optimize.ps1

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Birdman Fairing Optimizer" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$PythonExe = Join-Path $PSScriptRoot "vsp_env\Scripts\python.exe"
$MainScript = Join-Path $PSScriptRoot "scripts\main_optimization.py"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python not found at $PythonExe" -ForegroundColor Red
    exit 1
}

& $PythonExe $MainScript $args

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Optimization completed. Check output/ folder for results." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ERROR] Optimization failed. Check error messages above." -ForegroundColor Red
}
