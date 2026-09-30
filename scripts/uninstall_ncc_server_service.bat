@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall_ncc_service.ps1" -Component Server %*
if errorlevel 1 pause
