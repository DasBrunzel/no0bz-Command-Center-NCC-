@echo off
setlocal
set "NCC_MODE=server"
set "NCC_HOST=0.0.0.0"
echo [NCC] SERVER-Modus - Dashboard und Node-API laufen auf Port 8350.
echo [NCC] Clients benoetigen die LAN-IP dieses PCs und denselben NCC_TOKEN.
call "%~dp0start_ncc.bat"
