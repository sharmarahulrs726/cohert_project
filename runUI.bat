@echo off
chcp 65001 >nul
title Tax Investigation System

echo ========================================
echo   Tax Investigation System - Launcher
echo ========================================
echo.

:: Check if .venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Installing dependencies...
    call .venv\Scripts\pip.exe install -r requirements.txt
)

:: Ensure API dependencies are installed
echo [INFO] Checking API dependencies...
call .venv\Scripts\python.exe -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo [INFO] Installing API server dependencies...
    call .venv\Scripts\pip.exe install fastapi uvicorn python-multipart
)

:: Install frontend dependencies if needed
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

:: Start backend server
echo [INFO] Starting API server on http://localhost:8000...
start "API Server" cmd /c ".venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for API to start
timeout /t 3 /nobreak >nul

:: Check if API is actually running
echo [INFO] Verifying API server...
call .venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=2); print('[OK] API is running')" 2>nul || (
    echo [WARNING] API server not responding yet. Check the API Server window for errors.
    echo [INFO] If the API window closed immediately, try running this manually:
    echo        .venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
)

:: Start frontend dev server
echo [INFO] Starting frontend on http://localhost:5173...
cd frontend
start "Frontend" cmd /c "npx vite --host 0.0.0.0 --port 5173"
cd ..

echo.
echo ========================================
echo   API:       http://localhost:8000
echo   Frontend:  http://localhost:5173
echo   API Docs:  http://localhost:8000/docs
echo ========================================
echo.
echo If the frontend shows errors, check the API Server window for details.
echo.
pause
