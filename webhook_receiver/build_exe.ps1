# Build WebhookReceiver.exe (one-file) for end-user deploy.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install "pyinstaller>=6.0" tzdata

if (Test-Path .\dist) {
    try {
        Remove-Item -Recurse -Force .\dist
    } catch {
        Write-Host "WARNING: could not clear dist (EXE may be running). Building anyway..."
    }
}
if (Test-Path .\build) { Remove-Item -Recurse -Force .\build -EA SilentlyContinue }

.\.venv\Scripts\pyinstaller.exe --noconfirm WebhookReceiver.spec

$out = Join-Path $PSScriptRoot "dist\WebhookReceiver.exe"
if (-not (Test-Path $out)) {
    throw "Build failed: $out not found"
}

Write-Host ""
Write-Host "Built: $out"
Write-Host "Ship that EXE to users. On first launch it writes config.json next to the EXE."
