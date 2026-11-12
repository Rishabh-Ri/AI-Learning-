@echo off
cd /d %~dp0
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.10-3.12 from python.org and tick "Add Python to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Setup finished. Next: edit .env, then run  .venv\Scripts\python -m scripts.check_setup  and then run_all.bat
pause
