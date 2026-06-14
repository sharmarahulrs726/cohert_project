#!/usr/bin/env bash

set -e

# Project root = directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

# Create log directory
mkdir -p log

# Timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="log/log_run_${TIMESTAMP}.log"

echo "=================================================="
echo "Starting application..."
echo "Project: $SCRIPT_DIR"
echo "Log File: $LOGFILE"
echo "=================================================="

# Detect Python executable
if [ -f ".venv/bin/python" ]; then
    echo "[INFO] Linux/WSL virtualenv detected"
    PYTHON_CMD=".venv/bin/python"

elif [ -f ".venv/Scripts/python.exe" ]; then
    echo "[INFO] Windows virtualenv detected"
    PYTHON_CMD=".venv/Scripts/python.exe"

elif command -v python3 >/dev/null 2>&1; then
    echo "[WARN] No virtualenv found, using system python3"
    PYTHON_CMD="python3"

elif command -v python >/dev/null 2>&1; then
    echo "[WARN] No virtualenv found, using system python"
    PYTHON_CMD="python"

else
    echo "[ERROR] Python not found."
    exit 1
fi

echo "[INFO] Using: $PYTHON_CMD"
echo

# Run application and save all output
"$PYTHON_CMD" main.py 2>&1 | tee "$LOGFILE"

EXIT_CODE=${PIPESTATUS[0]}

echo
echo "=================================================="
echo "Finished with exit code: $EXIT_CODE"
echo "Log saved to: $LOGFILE"
echo "=================================================="

exit $EXIT_CODE