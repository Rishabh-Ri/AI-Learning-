@echo off
cd /d %~dp0
start "YouTube Service (Flask :5001)" cmd /k ".venv\Scripts\python.exe -m youtube_service.app"
start "Backend (FastAPI :8000)" cmd /k ".venv\Scripts\python.exe -m backend.run"
timeout /t 5 >nul
start http://127.0.0.1:8000
