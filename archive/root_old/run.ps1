# Quick launcher for VSP Python scripts (PowerShell version)
# Usage: .\run.ps1 script_name.py [arguments]

$PythonExe = Join-Path $PSScriptRoot "vsp_env\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Error: Python environment not found at $PythonExe" -ForegroundColor Red
    exit 1
}

if ($args.Count -eq 0) {
    Write-Host "Usage: .\run.ps1 script_name.py [arguments]" -ForegroundColor Yellow
    exit 1
}

& $PythonExe $args
