# Optional installer for SGG C1.0. Safe: never overwrites existing B1.0 files.
# Run from PowerShell with: powershell -ExecutionPolicy Bypass -File .\SETUP_C1.ps1
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$sourceBase='https://raw.githubusercontent.com/magiccozmo/QuackSink/main/ARCHIVES%208-30-2026/SGG/archives/SGG_23OCT26_08-31amVB1.0/'
foreach ($name in @('sggb1.0.py','luma_assets.json')) {
    if (Test-Path -LiteralPath $name) {
        Write-Host "Already available: $name (not modified)"
        continue
    }
    $local=Join-Path (Split-Path -Parent $PSScriptRoot) $name
    if (Test-Path -LiteralPath $local) {
        Copy-Item -LiteralPath $local -Destination (Join-Path $PSScriptRoot $name)
        Write-Host "Copied existing B1.0 file from parent: $name"
        continue
    }
    Write-Host "Downloading original B1.0 $name from the known October 23 archive..."
    Invoke-WebRequest -Uri ($sourceBase+$name) -OutFile (Join-Path $PSScriptRoot $name)
}
Write-Host ''
Write-Host 'Ready. Activate the SAME venv that runs B1.0, then run:'
Write-Host '   python sggc1.0.py'
