@echo off
title AI TrafficGuard - Real-Time Surveillance Engine
echo ==============================================================
echo [AI TrafficGuard] Traffic Violation Monitoring System
echo YOLOv8/v11 + BoT-SORT Vehicle Tracking + Check Zone Consensus
echo ==============================================================
echo.
cd /d "%~dp0backend"
echo [1/2] Initializing Surveillance Engine and Database...
echo [2/2] Launching AI TrafficGuard full-stack server on http://localhost:8000
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
