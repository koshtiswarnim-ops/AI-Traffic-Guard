@echo off
title AI TrafficGuard - Development Mode
echo ==============================================================
echo [AI TrafficGuard] Development Launcher (FastAPI + Vite Dev)
echo ==============================================================
echo.
start "AI TrafficGuard Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 /nobreak >nul
start "AI TrafficGuard Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo Both services launched! Access development UI on http://localhost:5173
echo Backend API available on http://localhost:8000
pause
