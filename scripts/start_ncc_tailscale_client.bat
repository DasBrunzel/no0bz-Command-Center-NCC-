@echo off
chcp 65001 >nul
setlocal
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
set "TOKENFILE=%~2"
if not defined TOKENFILE if exist "ncc-token-transfer.txt" set "TOKENFILE=ncc-token-transfer.txt"
if defined TOKENFILE (
  echo [NCC] Importiere gemeinsamen Server-Token aus %TOKENFILE%.
  "%PYTHON%" scripts\ncc_token.py import-file "%TOKENFILE%" || exit /b 1
)
"%PYTHON%" scripts\ncc_token.py check >nul 2>&1
if errorlevel 1 (
  echo [NCC] Importiere zuerst die vom Server erzeugte Token-Datei.
  set /p "TOKENFILE=Pfad zur Übergabedatei: "
  if not defined TOKENFILE exit /b 1
  "%PYTHON%" scripts\ncc_token.py import-file "%TOKENFILE%" || exit /b 1
)
for /f "delims=" %%U in ('%PYTHON% -m scripts.ncc_connection normalize "%TAILSCALE_TARGET%"') do set "NCC_SERVER_URL=%%U"
if not defined NCC_SERVER_URL (
  echo [FEHLER] Serveradresse konnte nicht verarbeitet werden.
  exit /b 1
)
set "NCC_MODE=client"
set "NCC_HOST=127.0.0.1"
for /f "delims=" %%T in ('%PYTHON% scripts\ncc_token.py value') do set "NCC_TOKEN=%%T"
echo [NCC] Prüfe Server und gemeinsamen Token ...
"%PYTHON%" -m scripts.ncc_connection check "%NCC_SERVER_URL%" || exit /b 1
echo [NCC] TAILSCALE-CLIENT - sende an %NCC_SERVER_URL%
call scripts\start_ncc.bat
