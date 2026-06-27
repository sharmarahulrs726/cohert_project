"""
Centralized path configuration for the Tax Investigation System.

All file-system paths are defined ONCE here, with Vercel vs local
distinction handled in a single place. Import this module wherever
you need access to any path.

Usage:
    from src.paths import OUTPUT_DIR, SAMPLE_DIR, IS_VERCEL, ...
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# ---------------------------------------------------------------------------
# Vercel / HF Spaces detection (single source of truth)
# ---------------------------------------------------------------------------
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("NOW_REGION"))
IS_HF_SPACES = bool(os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"))

# ---------------------------------------------------------------------------
# Writable directories (redirect to /tmp on Vercel/HF Spaces, use PROJECT_ROOT locally)
# ---------------------------------------------------------------------------
_WRITABLE_BASE = Path("/tmp") if (IS_VERCEL or IS_HF_SPACES) else PROJECT_ROOT

OUTPUT_DIR = _WRITABLE_BASE / "output"
AUDIT_DIR = _WRITABLE_BASE / "audit"
LOG_DIR = _WRITABLE_BASE / "logs"

# ---------------------------------------------------------------------------
# Input directories
# ---------------------------------------------------------------------------
# src-level input (set by init_config() at runtime)
INPUT_DIR: Path | None = None

# API directories
API_DIR = PROJECT_ROOT / "api"
if IS_VERCEL or IS_HF_SPACES:
    API_INPUT_BASE = Path("/tmp/input")
    API_OUTPUT_BASE = Path("/tmp/output")
else:
    API_INPUT_BASE = API_DIR / "input"
    API_OUTPUT_BASE = API_DIR / "output"

# ---------------------------------------------------------------------------
# Sample / template directories (read-only, works on Vercel from repo)
# ---------------------------------------------------------------------------
SAMPLE_DIR = PROJECT_ROOT / "sample"

# ---------------------------------------------------------------------------
# LibreOffice path (platform-aware)
# ---------------------------------------------------------------------------
LIBREOFFICE_CMD: str = os.getenv(
    "LIBREOFFICE_CMD",
    "soffice" if sys.platform == "win32" else "libreoffice",
)
