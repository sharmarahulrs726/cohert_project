@echo off
REM Tax Investigation System - Dev Launcher
REM Starts both FastAPI backend and React frontend

echo ========================================
echo  Tax Investigation System - Dev Mode
echo ========================================
echo.

REM Check if .venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run: py -3.11 -m venv .venv
    exit /b 1
)

REM Check if node_modules exists
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo [INFO] Starting FastAPI backend on http://localhost:8000
echo [INFO] Starting React frontend on http://localhost:5173
echo [INFO] Press Ctrl+C to stop both servers
echo.

REM Start API in background
start "Tax-API" cmd /c ".venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload"

REM Start frontend in foreground
cd frontend
call npx vite --host 127.0.0.1 --port 5173
cd ..

REM Cleanup: kill API when frontend stops
echo [INFO] Shutting down API server...
taskkill /f /fi "WINDOWTITLE eq Tax-API" >nul 2>&1
echo [INFO] Done.
