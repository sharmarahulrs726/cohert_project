@echo off
setlocal

REM Project root = location of this script
cd /d "%~dp0"

REM Create log directory if missing
if not exist "log" mkdir "log"

REM Generate timestamp: YYYYMMDD_HHMMSS
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i

set LOGFILE=log\log_run_%TS%.log

echo ==================================================
echo Starting application...
echo Log File: %LOGFILE%
echo ==================================================

call ".venv\Scripts\activate.bat"

py main.py 2>&1 | powershell -Command "$input | Tee-Object -FilePath '%LOGFILE%'"

echo.
echo Finished.
echo Log saved to: %LOGFILE%

pause