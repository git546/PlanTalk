$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Backend virtual environment is missing. Run .\scripts\setup.ps1 first."
}

& $venvPython -m uvicorn app.main:app --app-dir $backendDir --reload --host 0.0.0.0 --port 8000
