@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" python -m venv .venv
set "PYTHON=.venv\Scripts\python.exe"
"%PYTHON%" -m pip install -e . || exit /b 1
if not defined NCC_AGENT_SERVER_URL set /p "NCC_AGENT_SERVER_URL=NCC Server-URL (HTTPS oder Tailscale): "
if not defined NCC_AGENT_SERVER_URL (
  echo [FEHLER] Eine Server-URL ist erforderlich.
  pause
  exit /b 1
)
if not defined NCC_AGENT_TOKEN for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$s=Read-Host 'Individueller Agent-Token' -AsSecureString;$b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}"`) do set "NCC_AGENT_TOKEN=%%T"
if not defined NCC_AGENT_TOKEN (
  echo [FEHLER] Ein individueller Agent-Token ist erforderlich.
  pause
  exit /b 1
)
set "PYTHONPATH=backend"
echo [NCC] Starte den GUI-losen Agenten fuer %NCC_AGENT_SERVER_URL%.
"%PYTHON%" -m ncc_agent.main
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
