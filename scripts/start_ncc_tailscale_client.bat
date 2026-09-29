@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
set "TAILSCALE_TARGET=%~1"
if not defined TAILSCALE_TARGET set /p "TAILSCALE_TARGET=Tailscale-IP oder MagicDNS-Name des Servers: "
if not defined TAILSCALE_TARGET (
  echo [FEHLER] Serveradresse fehlt.
  pause
  exit /b 1
)
"%PYTHON%" scripts\ncc_token.py check >nul 2>&1
if errorlevel 1 (
  echo [NCC] Importiere zuerst die vom Server erzeugte Token-Datei.
  set /p "TOKENFILE=Pfad zur Übergabedatei: "
  "%PYTHON%" scripts\ncc_token.py import-file "!TOKENFILE!" || exit /b 1
)
set "NCC_MODE=client"
set "NCC_HOST=127.0.0.1"
set "NCC_SERVER_URL=http://%TAILSCALE_TARGET%:8350"
for /f "usebackq delims=" %%T in (`"%PYTHON%" scripts\ncc_token.py value`) do set "NCC_TOKEN=%%T"
echo [NCC] TAILSCALE-CLIENT - sende an %NCC_SERVER_URL%
call scripts\start_ncc.bat
