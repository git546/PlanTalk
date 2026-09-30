$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$mobileDir = Join-Path $repoRoot "mobile"
$backendDir = Join-Path $repoRoot "backend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

$nodeVersion = (& node --version).TrimStart("v")
if ([version]$nodeVersion -lt [version]"22.13.0") {
    throw "Expo SDK 57 requires Node.js 22.13 or newer. Current version: $nodeVersion"
}

$python312 = $null
try {
    & py -3.12 --version 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $python312 = "py"
    }
}
catch {
    $python312 = $null
}

if ($python312 -eq "py") {
    & py -3.12 --version | Out-Host
}
else {
    $uvPythonRoot = Join-Path $env:APPDATA "uv\python"
    $uvPython = Get-ChildItem -Path (Join-Path $uvPythonRoot "cpython-3.12.*-windows-x86_64-none\python.exe") -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $uvPython) {
        throw "Python 3.12 is required. Install it and run this script again."
    }
    $python312 = $uvPython.FullName
    & $python312 --version | Out-Host
}

Push-Location $mobileDir
try {
    & npm install
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($python312 -eq "py") {
        & py -3.12 -m venv $venvDir
    }
    else {
        & $python312 -m venv $venvDir
    }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e "$backendDir[dev]"

$backendEnv = Join-Path $backendDir ".env"
if (-not (Test-Path -LiteralPath $backendEnv)) {
    Copy-Item -LiteralPath (Join-Path $backendDir ".env.example") -Destination $backendEnv
}

$mobileEnv = Join-Path $mobileDir ".env.local"
if (-not (Test-Path -LiteralPath $mobileEnv)) {
    Copy-Item -LiteralPath (Join-Path $mobileDir ".env.example") -Destination $mobileEnv
}

Write-Host "PlanTalk development environment is ready." -ForegroundColor Green
Write-Host "API:    .\scripts\api.ps1"
Write-Host "Mobile: npm --prefix mobile start"
