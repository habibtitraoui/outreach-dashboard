@echo off
REM EduFormation outreach dashboard - one-click start (Windows)
REM Double-click this file. Then open:  http://localhost:8000

cd /d "%~dp0"

echo.
echo   EduFormation outreach dashboard
echo   -------------------------------

where python >nul 2>&1
if errorlevel 1 (
  echo   X python not found. Install it from https://python.org ^(tick "Add python.exe to PATH"^)
  echo.
  pause
  exit /b 1
)

echo   Starting... your browser will open at http://localhost:8000
echo   Keep this window open while you use the dashboard. Ctrl-C stops it.
echo.

start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000"
python app.py

echo.
echo   Server stopped.
pause
