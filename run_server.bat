@echo off
title BSG Sangareddy Portal - Live Server (127.0.0.1:8000)
cd /d "%~dp0"
echo =====================================================================
echo    BHARAT SCOUTS AND GUIDES - SANGAREDDY DISTRICT PORTAL
echo =====================================================================
echo.
echo Freeing port 8000 if previously occupied...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1

echo Checking database & settings...
python manage.py check
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Django checks failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =====================================================================
echo Starting web server on http://127.0.0.1:8000/
echo Keep this window open while using the website!
echo (Press Ctrl+C to stop the server)
echo =====================================================================
echo.
python manage.py runserver 127.0.0.1:8000
pause
