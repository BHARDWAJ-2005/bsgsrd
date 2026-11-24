@echo off
title Stop BSG Sangareddy Web Server
cd /d "%~dp0"
echo =====================================================================
echo    STOPPING BSG SANGAREDDY WEB SERVER (PORT 8000)
echo =====================================================================
echo.
set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo Freeing port 8000 (killing PID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
    set FOUND=1
)
if %FOUND%==1 (
    echo [SUCCESS] Server stopped and port 8000 is now free.
) else (
    echo [INFO] No server was running on port 8000.
)
echo.
pause
