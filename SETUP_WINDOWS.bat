@echo off
setlocal
cd /d "%~dp0"
echo =======================================================
echo SentinelIQ - First-time Windows Setup (research demo)
echo =======================================================
py -3.12 --version >nul 2>&1
if errorlevel 1 (
 echo Python 3.12 is required by this setup.
 echo Run: winget install --id Python.Python.3.12 -e
 echo Close and reopen this CMD window after installation.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements-core.txt
if errorlevel 1 goto fail
if not exist .env (
 copy .env.example .env >nul
 echo Config file .env created.
)
".venv\Scripts\python.exe" -c "from pathlib import Path; import secrets; p=Path('.env');s=p.read_text();placeholder='REPLACE_WITH_UNIQUE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS';p.write_text(s.replace(placeholder,secrets.token_urlsafe(48)))"
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m alembic -c backend\alembic.ini upgrade head
if errorlevel 1 goto fail
".venv\Scripts\python.exe" scripts\prepare_demo_models.py motor health travel
if errorlevel 1 goto fail
echo.
echo Model setup complete. Optional: activate all 14 categories in Admin ^& audit.
echo If this is your first install, create an admin now.
echo If you already have an admin login, press Enter to skip.
set /p ADMIN_EMAIL=Admin email (or Enter to skip): 
if not "%ADMIN_EMAIL%"=="" (
 ".venv\Scripts\python.exe" scripts\create_admin.py --email "%ADMIN_EMAIL%"
 if errorlevel 1 echo If this email already exists, sign in with the original password.
)
echo.
echo Setup completed without overwriting existing database records.
echo Double-click RUN_WINDOWS.bat to start the website.
pause
exit /b 0
:fail
echo Setup did not complete. Check the error above. Existing runtime data was not removed.
pause
exit /b 1
