@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
set "TAILSCALE_TARGET=%~1"
if not defined TAILSCALE_TARGET set /p "TAILSCALE_TARGET=Tailscale-IP oder MagicDNS-Name des Servers: "
if not defined TAILSCALE_TARGET exit /b 1
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
for /f "delims=" %%U in ('"%PYTHON%" -m scripts.ncc_connection normalize "%TAILSCALE_TARGET%"') do set "NCC_AGENT_SERVER_URL=%%U"
if not defined NCC_AGENT_SERVER_URL (
  echo [FEHLER] Tailscale-Adresse konnte nicht verarbeitet werden.
  pause
  exit /b 1
)
set "NCC_AGENT_ALLOW_INSECURE_HTTP=1"
call scripts\start_ncc_agent.bat
