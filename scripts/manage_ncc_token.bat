@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
:menu
cls
echo ==========================================
echo   NCC TOKEN MANAGER
echo ==========================================
echo [1] Token erstmalig erzeugen
echo [2] Token anzeigen
echo [3] Token rotieren und Exportdatei erzeugen
echo [4] Token in Datei exportieren
echo [5] Token-Datei auf diesem PC importieren
echo [6] Token manuell eingeben
echo [0] Beenden
echo.
set /p "CHOICE=Auswahl: "
if "%CHOICE%"=="1" "%PYTHON%" scripts\ncc_token.py generate
if "%CHOICE%"=="2" "%PYTHON%" scripts\ncc_token.py show
if "%CHOICE%"=="3" "%PYTHON%" scripts\ncc_token.py generate --force --export ncc-token-transfer.txt
if "%CHOICE%"=="4" "%PYTHON%" scripts\ncc_token.py export ncc-token-transfer.txt
if "%CHOICE%"=="5" (
  set /p "TOKENFILE=Pfad zur Übergabedatei: "
  "%PYTHON%" scripts\ncc_token.py import-file "!TOKENFILE!"
)
if "%CHOICE%"=="6" (
  set /p "NEWTOKEN=Token: "
  "%PYTHON%" scripts\ncc_token.py import-value "!NEWTOKEN!"
)
if "%CHOICE%"=="0" exit /b 0
echo.
pause
goto menu
