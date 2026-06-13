#!/usr/bin/env bash
#
# run.sh — Linux/macOS launcher for the Tax Investigation System
#
# Usage:
#   chmod +x run.sh && ./run.sh
#   ./run.sh --dry-run
#   ./run.sh --case CASE_001
#   ./run.sh --input /path/to/cases
#
# This script:
#   1. Checks for Python 3.11+
#   2. Installs dependencies via `uv` (if available) or pip + .venv
#   3. Runs main.py passing all command-line arguments through
#
# All print() output from the pipeline is shown on the terminal.
#
# Logs:
#   - Console output is mirrored to log files in log/ directory
#   - Log filenames include date and timestamp
#   - Logs help troubleshoot issues when double-clicking closes the window
# ==============================================================================

set -uo pipefail -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Create log directory if it doesn't exist
mkdir -p log

# Generate timestamp for log filename
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="log"
LOG_FILE="$LOG_DIR/$TIMESTAMP.log"

# Function to log messages to both console and log file
log_message() {
    local msg="$1"
    echo "$msg" | tee -a "$LOG_FILE"
}

# Initialize log with header
{
    echo "================================================================================"
    echo "RUN.SH - Linux/macOS Launcher Log File"
    echo "Started: $(date -Iseconds)"
    echo "================================================================================"
    echo ""
} | tee -a "$LOG_FILE"

# Redirect all stdout and stderr to log file AND console
exec > >(tee -a "$LOG_FILE")
exec 2 > >(tee -a "$LOG_FILE" >&2)

PYTHON=""
VENV_DIR=".venv"
REQUIREMENTS="requirements.txt"

# Bail early if requirements file is missing
[ -f "$REQUIREMENTS" ] || {
    echo "[ERROR] $REQUIREMENTS not found in $(pwd)"
    exit 1
}

# ------------------------------------------------------------------
# Step 1 — Find a suitable Python 3 interpreter
# ------------------------------------------------------------------
find_python() {
    log_message "[FIND_PYTHON] Searching for Python 3.11+..."
    for candidate in python3 python; do
        if command -v "$candidate" &>/dev/null; then
            ver_full=$("$candidate" --version 2>&1 | head -1)
            ver_num=$(echo "$ver_full" | cut -d' ' -f2)
            major=$(echo "$ver_num" | cut -d'.' -f1)
            minor=$(echo "$ver_num" | cut -d'.' -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                PYTHON="$candidate"
                log_message "[FIND_PYTHON] Found Python at: $PYTHON"
                return 0
            fi
        fi
    done
    log_message "[ERROR] Python 3.11+ not found. Please install Python 3.11 or later."
    exit 1
}

find_python
echo "[INFO] Using: $("$PYTHON" --version 2>&1)"

# ------------------------------------------------------------------
# Step 2 — Install dependencies
# ------------------------------------------------------------------
install_deps() {
    if command -v uv &>/dev/null; then
        log_message "[INSTALL_DEPS] uv detected — installing dependencies via uv..."
        uv pip install --system -r "$REQUIREMENTS" 2>/dev/null \
            || uv pip install -r "$REQUIREMENTS" 2>/dev/null \
            || {
                log_message "[WARN] uv install failed, falling back to pip..."
                pip_install
            }
        log_message "[INSTALL_DEPS] uv install complete."
    else
        log_message "[INSTALL_DEPS] uv not found — using pip with virtual environment."
        pip_install
    fi
}

pip_install() {
    if [ ! -d "$VENV_DIR" ]; then
        log_message "[PIP_INSTALL] Creating virtual environment at $VENV_DIR..."
        $PYTHON -m venv "$VENV_DIR"
    fi

    # Activate
    # shellcheck disable=SC1091
    [ -f "$VENV_DIR/bin/activate" ] || {
        log_message "[ERROR] Virtual environment activation failed."
        exit 1
    }
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    log_message "[PIP_INSTALL] Upgrading pip..."
    pip install --upgrade pip --quiet

    # Install requirements
    log_message "[PIP_INSTALL] Installing requirements from $REQUIREMENTS..."
    pip install -r "$REQUIREMENTS" || {
        log_message "[ERROR] pip install failed."
        exit 1
    }

    log_message "[PIP_INSTALL] pip install complete. Venv: $VENV_DIR"
}

install_deps

# ------------------------------------------------------------------
# Step 3 — Run main.py with all arguments forwarded
# ------------------------------------------------------------------
echo ""
log_message "[RUN] Running pipeline..."
log_message "[RUN] python main.py $@"
echo ""

if [ -n "${VIRTUAL_ENV:-}" ]; then
    log_message "[RUN] Using venv: $VIRTUAL_ENV"
    python main.py "$@"
else
    log_message "[RUN] Using system python: $PYTHON"
    "$PYTHON" main.py "$@"
fi

exit_code=$?
if [ $exit_code -eq 0 ]; then
    log_message "[DONE] Pipeline finished successfully."
else
    log_message "[ERROR] Pipeline exited with code $exit_code."
fi
exit $exit_code
