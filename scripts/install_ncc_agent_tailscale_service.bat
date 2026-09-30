@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_ncc_service.ps1" -Component Agent -Tailscale
if errorlevel 1 pause
