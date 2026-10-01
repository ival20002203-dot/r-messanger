param(
    [string]$ServerUrl = ""
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
Set-Location $Root
if($ServerUrl){ & "$PSScriptRoot\configure_clients.ps1" -ServerUrl $ServerUrl }
Write-Host "=== R-Mes 15 Windows ===" -ForegroundColor Cyan
& "$Root\desktop\build_windows.ps1"
Write-Host "=== R-Mes 15 Android ===" -ForegroundColor Cyan
& "$Root\mobile\android\build_apk_windows.ps1"
Write-Host "iPhone source is ready in mobile\ios\RMesIOS.xcodeproj (requires macOS/Xcode signing)." -ForegroundColor Yellow
