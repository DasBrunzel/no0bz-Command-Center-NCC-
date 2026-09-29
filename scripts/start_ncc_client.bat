@echo off
setlocal
set "NCC_MODE=client"
set "NCC_HOST=127.0.0.1"
if not defined NCC_SERVER_URL set /p "NCC_SERVER_URL=Server-URL (z.B. http://192.168.1.10:8350): "
if not defined NCC_SERVER_URL (
  echo [FEHLER] Eine Server-URL ist erforderlich.
  pause
  exit /b 1
)
if not defined NCC_TOKEN set /p "NCC_TOKEN=NCC_TOKEN des Servers: "
if not defined NCC_TOKEN (
  echo [FEHLER] Der gemeinsame Server-Token ist erforderlich.
  pause
  exit /b 1
)
echo [NCC] CLIENT-Modus - sende Telemetrie an %NCC_SERVER_URL%.
call "%~dp0start_ncc.bat"
