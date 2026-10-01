@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_clients_windows.ps1" %*
