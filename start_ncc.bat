@echo off
title no0bz Command Center (NCC) v3.9.0
echo ========================================================
echo   Starting no0bz Command Center (NCC) v3.9.0...
echo   Web GUI Port:       8350
echo   Dedicated Remote:   8351 (Multi-PC Cluster Hub)
echo ========================================================
python -m pip install -r requirements.txt
echo.
echo Launching Web GUI at http://localhost:8350 ...
start "" "http://localhost:8350"
python main.py %*
pause

