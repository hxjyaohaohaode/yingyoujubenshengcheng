@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

echo ============================================
echo   Starting Script Engine Servers
echo ============================================
echo.

cd /d "%SCRIPT_DIR%backend"
echo [1/2] Starting Backend Server (port 8000)...
echo Loading environment from .env file if present...
if exist ".env" (
    for /f "usebackq tokens=*" %%a in (".env") do (
        set "line=%%a"
        if not "!line!"=="" if not "!line:~0,1!"=="#" set %%a >nul 2>nul
    )
)
start "Backend Server" cmd /k "python -m uvicorn main:app --port 8000 --reload"

timeout /t 3 /nobreak >nul

cd /d "%SCRIPT_DIR%frontend"
echo [2/2] Starting Frontend Server (port 5173)...
start "Frontend Server" cmd /k "npm run dev"

echo.
echo ============================================
echo   Servers are starting!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ============================================
echo.
echo Make sure your .env file is configured with:
echo   - DEEPSEEK_API_KEY
echo   - MIMO_API_KEY
echo ============================================
timeout /t 10