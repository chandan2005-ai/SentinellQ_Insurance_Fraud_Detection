@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run SETUP_WINDOWS.bat first.
 pause
 exit /b 1
)
echo SentinelIQ website: http://127.0.0.1:8000
echo Keep this command window open. Close it to stop the website.
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
pause
