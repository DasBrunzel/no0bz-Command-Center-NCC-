@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
for /f "usebackq delims=" %%I in (`"%PYTHON%" scripts\tailscale_ip.py`) do set "NCC_HOST=%%I"
if not defined NCC_HOST (
  echo [FEHLER] Keine aktive Tailscale-IP gefunden.
  echo Starte Tailscale und versuche es erneut.
  pause
  exit /b 1
)
"%PYTHON%" scripts\ncc_token.py check >nul 2>&1
if errorlevel 1 (
  echo [NCC] Es ist noch kein gemeinsamer Token vorhanden.
  "%PYTHON%" scripts\ncc_token.py generate --export ncc-token-transfer.txt
)
set "NCC_MODE=server"
echo [NCC] TAILSCALE-SERVER: http://%NCC_HOST%:8350
echo [NCC] Nur die Tailscale-Schnittstelle wird gebunden.
call scripts\start_ncc.bat
