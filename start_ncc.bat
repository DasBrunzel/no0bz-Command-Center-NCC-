@echo off
title no0bz Command Center (NCC) v3.8.1
echo ========================================================
echo   Starting no0bz Command Center (NCC) v3.8.1...
echo ========================================================
python -m pip install -r requirements.txt
echo.
echo Launching Web GUI at http://localhost:8350 ...
start "" "http://localhost:8350"
python main.py
pause
