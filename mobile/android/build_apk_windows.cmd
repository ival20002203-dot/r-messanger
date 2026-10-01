@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_apk_windows.ps1"
if errorlevel 1 pause
endlocal
