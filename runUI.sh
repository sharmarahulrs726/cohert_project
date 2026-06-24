#!/usr/bin/env bash
set -e

# Project root = directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Tax Investigation System - Launcher"
echo "========================================"
echo ""

# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------
detect_python() {
    if [ -f ".venv/bin/python" ]; then
        PYTHON_CMD=".venv/bin/python"
        PIP_CMD=".venv/bin/pip"
    elif [ -f ".venv/Scripts/python.exe" ]; then
        PYTHON_CMD=".venv/Scripts/python.exe"
        PIP_CMD=".venv/Scripts/pip.exe"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
        PIP_CMD="pip"
    else
        echo "[ERROR] Python not found."
        exit 1
    fi
}

detect_python
echo "[INFO] Python: $PYTHON_CMD"

# ---------------------------------------------------------------------------
# Create virtual environment if missing
# ---------------------------------------------------------------------------
if [ ! -f ".venv/bin/python" ] && [ ! -f ".venv/Scripts/python.exe" ]; then
    echo "[INFO] Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    echo "[INFO] Installing dependencies..."
    $PIP_CMD install -r requirements.txt
    detect_python  # re-detect after venv creation
fi

# ---------------------------------------------------------------------------
# Ensure API dependencies are installed
# ---------------------------------------------------------------------------
echo "[INFO] Checking API dependencies..."
$PYTHON_CMD -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "[INFO] Installing API server dependencies..."
    $PIP_CMD install fastapi uvicorn python-multipart
}

# ---------------------------------------------------------------------------
# Install frontend dependencies if needed
# ---------------------------------------------------------------------------
if [ ! -d "frontend/node_modules" ]; then
    echo "[INFO] Installing frontend dependencies..."
    cd frontend
    npm install
    cd "$SCRIPT_DIR"
fi

# ---------------------------------------------------------------------------
# Cleanup handler — kill background processes on exit
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "[INFO] Shutting down servers..."
    if [ -n "$API_PID" ]; then
        kill "$API_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "[INFO] Done."
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Start backend server
# ---------------------------------------------------------------------------
echo "[INFO] Starting API server on http://localhost:8000..."
$PYTHON_CMD -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# Wait for API to start
sleep 3

# Verify API is running
echo "[INFO] Verifying API server..."
if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "[OK] API is running"
else
    echo "[WARNING] API server not responding yet. Check the output above for errors."
    echo "[INFO] Try running manually:"
    echo "       $PYTHON_CMD -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
fi

# ---------------------------------------------------------------------------
# Start frontend dev server
# ---------------------------------------------------------------------------
echo "[INFO] Starting frontend on http://localhost:5173..."
cd frontend
npx vite --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  API:       http://localhost:8000"
echo "  Frontend:  http://localhost:5173"
echo "  API Docs:  http://localhost:8000/docs"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

# Wait for either process to exit
wait $API_PID $FRONTEND_PID
