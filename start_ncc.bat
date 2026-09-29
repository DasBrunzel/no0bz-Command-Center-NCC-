@echo off
title no0bz Command Center (NCC) v3.12.0
echo ========================================================
echo   Starting no0bz Command Center (NCC) v3.12.0...
echo   Web GUI Port:       8350
echo   Nexus Rig Matrix:   Cluster Ready
echo ========================================================
python -m pip install -r requirements.txt
echo.
echo Launching Web GUI at http://localhost:8350 ...
start "" "http://localhost:8350"
python main.py %*
pause

