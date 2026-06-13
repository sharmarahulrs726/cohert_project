@echo off
REM ============================================================================
REM  run.bat — Windows launcher for the Tax Investigation System
REM
REM  Usage:
REM      run.bat
REM      run.bat --dry-run
REM      run.bat --case CASE_001
REM      run.bat --input C:\path\to\cases
REM
REM  This script:
REM    1. Checks for Python 3.11+
REM    2. Installs dependencies via `uv` (if available) or pip + .venv
REM    3. Runs main.py passing all command-line arguments through
REM
REM  All print() output from the pipeline is shown on the terminal.
REM
REM  Logs:
REM    - Console output is mirrored to log files in log/ directory
REM    - Log filenames include date and timestamp
REM    - Logs help troubleshoot issues when double-clicking closes the window
REM ============================================================================

setlocal enabledelayedexpansion
pushd "%~dp0"

REM Create log directory if it doesn't exist
if not exist "log" mkdir log

REM Generate timestamp for log filename
for /f "tokens=2 delims==" %%a in ('wmic os get LocalDateTime /value') do set "TIMESTAMP=%%a"
set "LOG_DIR=log"
set "LOG_FILE=%LOG_DIR%\%TIMESTAMP%.log"

REM Initialize log with header
(
echo ============================================================================
echo RUN.SH - Windows Launcher Log File
echo Started: %TIMESTAMP%
echo ============================================================================
echo.
) >> "%LOG_FILE%"

echo Log file: %LOG_FILE%

set "VENV_DIR=.venv"
set "REQUIREMENTS=requirements.txt"

REM Bail early if requirements file is missing
if not exist "%REQUIREMENTS%" (
    echo [ERROR] %REQUIREMENTS% not found in %cd%
    popd
    exit /b 1
)

REM ------------------------------------------------------------------
REM Step 1 — Find Python 3
REM ------------------------------------------------------------------
:find_python
echo [FIND_PYTHON] Searching for Python...
echo [FIND_PYTHON] Searching for Python... >> "%LOG_FILE%"
set "PYTHON="

where python >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    if defined PY_VER (
        for /f "tokens=1 delims=." %%m in ("!PY_VER!") do set "PY_MAJOR=%%m"
        for /f "tokens=2 delims=." %%m in ("!PY_VER!") do set "PY_MINOR=%%m"
    )
    if defined PY_MAJOR if !PY_MAJOR! geq 3 if !PY_MINOR! geq 11 (
        set "PYTHON=python"
        goto :found_python
    )
)

where py >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set "PY_VER=%%v"
    if defined PY_VER (
        for /f "tokens=1 delims=." %%m in ("!PY_VER!") do set "PY_MAJOR=%%m"
        for /f "tokens=2 delims=." %%m in ("!PY_VER!") do set "PY_MINOR=%%m"
    )
    if defined PY_MAJOR if !PY_MAJOR! geq 3 if !PY_MINOR! geq 11 (
        set "PYTHON=py"
        goto :found_python
    )
)

echo [ERROR] Python 3.11+ not found. Please install Python 3.11 or later.
pause
popd
exit /b 1

:found_python
!PYTHON! --version
echo [INFO] Using: !PYTHON!

REM ------------------------------------------------------------------
REM Step 2 — Install dependencies
REM ------------------------------------------------------------------
:install_deps
echo [INSTALL_DEPS] Installing dependencies...
echo [INSTALL_DEPS] Installing dependencies... >> "%LOG_FILE%"
where uv >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] uv detected — installing dependencies via uv...
    echo [INFO] uv detected — installing dependencies via uv... >> "%LOG_FILE%"
    uv pip install --system -r !REQUIREMENTS!
    set "UV_EXIT=!errorlevel!"
    if !UV_EXIT! neq 0 (
        uv pip install -r !REQUIREMENTS!
        set "UV_EXIT=!errorlevel!"
    )
    if !UV_EXIT! neq 0 (
        echo [WARN] uv install failed, falling back to pip...
        echo [WARN] uv install failed, falling back to pip... >> "%LOG_FILE%"
        call :pip_install
        if !errorlevel! neq 0 (
            popd
            exit /b !errorlevel!
        )
    ) else (
        echo [INFO] uv install complete.
        echo [INFO] uv install complete... >> "%LOG_FILE%"
    )
) else (
    echo [INFO] uv not found — using pip with virtual environment.
    echo [INFO] uv not found — using pip with virtual environment... >> "%LOG_FILE%"
    call :pip_install
    if !errorlevel! neq 0 (
        popd
        exit /b !errorlevel!
    )
)
goto :run_main

:pip_install
if not exist "!VENV_DIR!" (
    echo [INFO] Creating virtual environment at !VENV_DIR!...
    echo [INFO] Creating virtual environment at !VENV_DIR!... >> "%LOG_FILE%"
    py -3.11 -m venv !VENV_DIR!
)

REM Activate venv
if exist "!VENV_DIR!\Scripts\Activate.ps1" (
    call "!VENV_DIR!\Scripts\Activate.ps1"
) else (
    echo [ERROR] Virtual environment activation failed.
    echo [ERROR] Virtual environment activation failed... >> "%LOG_FILE%"
    exit /b 1
)

REM Upgrade pip
echo [INFO] Upgrading pip...
echo [INFO] Upgrading pip... >> "%LOG_FILE%"
pip install --upgrade pip --quiet

REM Install requirements
echo [INFO] Installing requirements from !REQUIREMENTS!...
echo [INFO] Installing requirements from !REQUIREMENTS!... >> "%LOG_FILE%"
pip install -r !REQUIREMENTS!
if !errorlevel! neq 0 (
    echo [ERROR] pip install failed.
    echo [ERROR] pip install failed... >> "%LOG_FILE%"
    exit /b 1
)

echo [INFO] pip install complete. Venv: !VENV_DIR!
echo [INFO] pip install complete. Venv: !VENV_DIR!... >> "%LOG_FILE%"
exit /b 0

REM ------------------------------------------------------------------
REM Step 3 — Run main.py with all arguments forwarded
REM ------------------------------------------------------------------
:run_main
echo.
echo [RUN] Running pipeline...
echo [RUN] Running pipeline... >> "%LOG_FILE%"

REM Execute the pipeline and capture exit code immediately
if defined VIRTUAL_ENV (
    echo [RUN] Using venv: !VIRTUAL_ENV!
    echo [RUN] Using venv: !VIRTUAL_ENV!... >> "%LOG_FILE%"
    python main.py %*
    set "EXIT_CODE=!errorlevel!"
) else (
    echo [RUN] Using system python: !PYTHON!
    echo [RUN] Using system python: !PYTHON!... >> "%LOG_FILE%"
    !PYTHON! main.py %*
    set "EXIT_CODE=!errorlevel!"
)

if !EXIT_CODE! equ 0 (
    echo [DONE] Pipeline finished successfully.
    echo [DONE] Pipeline finished successfully... >> "%LOG_FILE%"
) else (
    echo [ERROR] Pipeline exited with code !EXIT_CODE!.
    echo [ERROR] Pipeline exited with code !EXIT_CODE!... >> "%LOG_FILE%"
)

popd
exit /b !EXIT_CODE!
