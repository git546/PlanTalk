param(
  [string]$Python = "C:\Users\OSY\AppData\Local\Programs\Python\Python311\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $ProjectRoot ".build\sensor-gateway"
$VenvRoot = Join-Path $BuildRoot "venv"
$PyInstallerRoot = Join-Path $BuildRoot "pyinstaller"
$ReleaseRoot = Join-Path $PSScriptRoot "release"
$PackageRoot = Join-Path $ReleaseRoot "PlanTalk-Sensor-Gateway"
$ZipPath = Join-Path $ReleaseRoot "PlanTalk-Sensor-Gateway-Windows.zip"
$EntryPath = Join-Path $PSScriptRoot "desktop_entry.py"

if (-not (Test-Path -LiteralPath $Python)) {
  throw "Python 3.11 실행 파일을 찾지 못했습니다: $Python"
}
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $VenvRoot "Scripts\python.exe"))) {
  & $Python -m venv $VenvRoot
}
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"

& $VenvPython -m pip install --disable-pip-version-check `
  -r (Join-Path $PSScriptRoot "requirements.txt") `
  "pyinstaller>=6.11,<7.0"
if ($LASTEXITCODE -ne 0) {
  throw '게이트웨이 빌드 의존성 설치에 실패했습니다.'
}

$DistRoot = Join-Path $PyInstallerRoot "dist"
$WorkRoot = Join-Path $PyInstallerRoot "work"
$SpecRoot = Join-Path $PyInstallerRoot "spec"
New-Item -ItemType Directory -Path $DistRoot, $WorkRoot, $SpecRoot -Force | Out-Null

Push-Location $ProjectRoot
try {
  & $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "PlanTalk-Sensor-Gateway" `
    --collect-all serial `
    --paths $ProjectRoot `
    --distpath $DistRoot `
    --workpath $WorkRoot `
    --specpath $SpecRoot `
    $EntryPath
  if ($LASTEXITCODE -ne 0) {
    throw '게이트웨이 실행 파일 빌드에 실패했습니다.'
  }
}
finally {
  Pop-Location
}

New-Item -ItemType Directory -Path $PackageRoot -Force | Out-Null
Copy-Item -LiteralPath (
  Join-Path $PyInstallerRoot "dist\PlanTalk-Sensor-Gateway.exe"
) -Destination (Join-Path $PackageRoot "PlanTalk-Sensor-Gateway.exe") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "TEAM_README.txt") `
  -Destination (Join-Path $PackageRoot "사용안내.txt") -Force

$PackageFiles = @(
  (Join-Path $PackageRoot "PlanTalk-Sensor-Gateway.exe"),
  (Join-Path $PackageRoot "사용안내.txt")
)
Compress-Archive -LiteralPath $PackageFiles -DestinationPath $ZipPath -Force

Write-Output "Release folder: $PackageRoot"
Write-Output "Release zip: $ZipPath"

