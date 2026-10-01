@echo off
setlocal
cd /d "%~dp0"
echo === R-Messanger Desktop 15.1.1 ===
echo Server: http://10.10.10.130:8000
where npm.cmd >nul 2>nul || (echo ERROR: Node.js/npm is not installed.& exit /b 1)
call npm.cmd install || exit /b 1
call npm.cmd run dist:win || exit /b 1
call npm.cmd run dist:gpo || exit /b 1
echo.
echo READY:
dir /b dist\RMes-*
endlocal
