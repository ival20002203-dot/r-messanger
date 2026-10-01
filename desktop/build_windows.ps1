$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "=== R-Messanger Desktop 15.1.1 ===" -ForegroundColor Cyan
Write-Host "Server URL is configured in desktop/main.js or R_MES_URL"
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "Node.js/npm is not installed" }
Write-Host "Installing/updating Node dependencies..."
npm.cmd install
Write-Host "Building Windows EXE..."
npm.cmd run dist:win
Write-Host "Building MSI for GPO..."
npm.cmd run dist:gpo
Write-Host ""
Write-Host "READY:" -ForegroundColor Cyan
Get-ChildItem "$PSScriptRoot\dist\RMes-*" | Select-Object Name,Length,LastWriteTime
