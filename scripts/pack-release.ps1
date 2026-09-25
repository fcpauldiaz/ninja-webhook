# Builds distribution artifacts under release\:
#   WebhookReceiver.exe
#   WebhookTradeListener-AddOn.zip   (NinjaTrader Tools → Import → NinjaScript Add-On)
#   NinjaWebhook-Portable.zip
#   NinjaWebhook-Setup.exe           (if Inno Setup 6 is installed)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\pack-release.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$release = Join-Path $root "release"
$staging = Join-Path $release "_staging"
$addonStaging = Join-Path $staging "addon"
$portableStaging = Join-Path $staging "portable"

Write-Host "==> Cleaning release\"
if (Test-Path $release) {
    Get-ChildItem $release -Force | Where-Object { $_.Name -ne "_staging" } | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $release | Out-Null
}
Remove-Item -Recurse -Force $staging -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path $addonStaging, $portableStaging | Out-Null

# --- Sync latest Add-On sources from installed NT Custom (if present) ---
$ntAddOns = Join-Path $env:USERPROFILE "Documents\NinjaTrader 8\bin\Custom\AddOns"
$projectNt = Join-Path $root "NinjaTrader"
$addonFiles = @(
    "WebhookTradeListener.cs",
    "WebhookTradeCommand.cs",
    "WebhookDuplicateCache.cs"
)
foreach ($f in $addonFiles) {
    $fromNt = Join-Path $ntAddOns $f
    $dest = Join-Path $projectNt $f
    if (Test-Path $fromNt) {
        Copy-Item -Force $fromNt $dest
        Write-Host "Synced $f from NT Custom"
    }
    if (-not (Test-Path $dest)) {
        throw "Missing Add-On source: $dest"
    }
}

# --- Build WebhookReceiver.exe ---
Write-Host "==> Building WebhookReceiver.exe"
$buildScript = Join-Path $root "webhook_receiver\build_exe.ps1"
powershell -ExecutionPolicy Bypass -File $buildScript
$builtExe = Join-Path $root "webhook_receiver\dist\WebhookReceiver.exe"
if (-not (Test-Path $builtExe)) {
    throw "EXE build failed: $builtExe not found"
}
Copy-Item -Force $builtExe (Join-Path $release "WebhookReceiver.exe")

# --- NinjaScript import zip (AddOns\*.cs at zip root — NT import layout) ---
Write-Host "==> Creating WebhookTradeListener-AddOn.zip"
$addonZipDir = Join-Path $addonStaging "AddOns"
New-Item -ItemType Directory -Force -Path $addonZipDir | Out-Null
foreach ($f in $addonFiles) {
    Copy-Item -Force (Join-Path $projectNt $f) (Join-Path $addonZipDir $f)
}
$addonZip = Join-Path $release "WebhookTradeListener-AddOn.zip"
if (Test-Path $addonZip) { Remove-Item -Force $addonZip }
# Compress so zip root contains AddOns\... (not an extra parent folder)
Push-Location $addonStaging
Compress-Archive -Path "AddOns" -DestinationPath $addonZip -Force
Pop-Location

# Verify zip entries
Add-Type -AssemblyName System.IO.Compression.FileSystem
$entries = [IO.Compression.ZipFile]::OpenRead($addonZip).Entries | ForEach-Object { $_.FullName }
[IO.Compression.ZipFile]::OpenRead($addonZip).Dispose()
Write-Host "Add-On zip entries:"
$entries | ForEach-Object { Write-Host "  $_" }
$expected = $addonFiles | ForEach-Object { "AddOns/$_" -replace '\\','/' }
# Windows zip may use backslash
$ok = $true
foreach ($f in $addonFiles) {
    $match = $entries | Where-Object { $_ -replace '\\','/' -eq "AddOns/$f" }
    if (-not $match) { Write-Host "MISSING in zip: AddOns/$f"; $ok = $false }
}
if (-not $ok) { throw "Add-On zip layout invalid" }

# --- Portable zip ---
Write-Host "==> Creating NinjaWebhook-Portable.zip"
Copy-Item -Force (Join-Path $release "WebhookReceiver.exe") $portableStaging
Copy-Item -Force $addonZip $portableStaging
Copy-Item -Force (Join-Path $root "packaging\DISTRIBUTION.md") $portableStaging
Copy-Item -Force (Join-Path $root "FLOW_TRADING.md") $portableStaging
Copy-Item -Force (Join-Path $root "OPTIONS_TRADING.md") $portableStaging
Copy-Item -Force (Join-Path $root "scripts\start-ngrok-tunnel.cmd") $portableStaging
$portableZip = Join-Path $release "NinjaWebhook-Portable.zip"
if (Test-Path $portableZip) { Remove-Item -Force $portableZip }
Compress-Archive -Path (Join-Path $portableStaging "*") -DestinationPath $portableZip -Force

# --- Inno Setup installer (optional) ---
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "==> Inno Setup not found - attempting winget install"
    try {
        winget install --id JRSoftware.InnoSetup -e --accept-source-agreements --accept-package-agreements | Out-Host
    } catch {
        Write-Host "winget install failed: $($_.Exception.Message)"
    }
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if ($iscc) {
    Write-Host "==> Building installer with $iscc"
    & $iscc (Join-Path $root "packaging\NinjaWebhook.iss")
    if (-not (Test-Path (Join-Path $release "NinjaWebhook-Setup.exe"))) {
        Write-Host "WARNING: NinjaWebhook-Setup.exe was not produced"
    }
} else {
    Write-Host "==> Skipping installer (Inno Setup 6 / ISCC.exe not available)"
    Write-Host "    Install from https://jrsoftware.org/isinfo.php then re-run this script"
}

Remove-Item -Recurse -Force $staging -EA SilentlyContinue

# --- Trade Desky public download names (trade-receiver /desktop aliases) ---
Write-Host "==> Writing TradeDeskyNinjaTraderReceiver publish names"
$versionPy = Join-Path $root "webhook_receiver\version.py"
$version = (
    Select-String -Path $versionPy -Pattern '__version__\s*=\s*"([^"]+)"' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } |
    Select-Object -First 1
)
if (-not $version) { throw "Could not read version from webhook_receiver\version.py" }

$tdSetup = Join-Path $release "TradeDeskyNinjaTraderReceiver-$version-setup.exe"
$tdZip = Join-Path $release "TradeDeskyNinjaTraderReceiver-$version-win.zip"
$setupSrc = Join-Path $release "NinjaWebhook-Setup.exe"
if (Test-Path $setupSrc) {
    Copy-Item -Force $setupSrc $tdSetup
} else {
    Write-Host "WARNING: $setupSrc missing — TradeDesky setup alias not written"
}
Copy-Item -Force $portableZip $tdZip

python (Join-Path $root "scripts\write_appcast.py") --release $release --version $version
if ($LASTEXITCODE -ne 0) { throw "write_appcast.py failed" }

Write-Host ""
Write-Host ("Release artifacts in {0}:" -f $release)
Get-ChildItem $release -File | Format-Table Name, Length, LastWriteTime -AutoSize
