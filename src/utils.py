"""
Shared utility helpers for the Tax Investigation System.

Provides commonly used functions for hashing, ISO timestamps,
safe decimal parsing, and directory creation.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports (graceful fallback)
# ---------------------------------------------------------------------------
try:
    from docling.document_converter import DocumentConverter
except Exception as e:
    logger.debug("docling not available: %s", e)
    DocumentConverter = None

try:
    from docxtpl import DocxTemplate
except Exception as e:
    logger.debug("docxtpl not available: %s", e)
    DocxTemplate = None

try:
    from openpyxl import load_workbook
except Exception as e:
    logger.debug("openpyxl not available: %s", e)
    load_workbook = None

try:
    from docx import Document
except Exception as e:
    logger.debug("python-docx not available: %s", e)
    Document = None


# ---------------------------------------------------------------------------
# File / hashing helpers
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    """Compute SHA‑256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    """Return the current UTC time as an ISO‑8601 string with Z suffix."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------
def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert a value to Decimal, stripping currency symbols."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    s = str(value).strip()
    if not s:
        return default

    s = s.replace(",", "").strip()
    # Strip any non-numeric prefix (currency symbols, words like INR, Rs, etc.)
    # Uses [^-\d] so dots in "Rs." are also stripped, while negative signs are preserved
    s = re.sub(r"^[^-\d]+", "", s).strip()
    try:
        return Decimal(s) if s else default
    except (ValueError, InvalidOperation):
        logger.debug("safe_decimal failed for '%s': not a valid number", s)
        return default


# ---------------------------------------------------------------------------
# Directory helper
# ---------------------------------------------------------------------------
def ensure_dir(path: Path) -> Path:
    """Create directory (parents as needed) and return the path.
    Falls back to /tmp if permission denied on primary path.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except PermissionError:
        fallback = Path("/tmp") / path.name
        logger.warning("Permission denied for %s, falling back to %s", path, fallback)
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    except OSError as e:
        fallback = Path("/tmp") / path.name
        logger.warning("Failed to create %s (%s), falling back to %s", path, e, fallback)
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
