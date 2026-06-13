"""
Configuration module for the Tax Investigation System.

Handles directory auto-detection, template path discovery,
and all configurable constants used throughout the system.

Usage:
    from src.config import BASE_DIR, init_config
    init_config()  # bootstraps directories and detects templates
"""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default base paths (can be overridden via environment or direct assignment)
# ---------------------------------------------------------------------------
BASE_DIR = Path.cwd()
SAMPLE_DIR = BASE_DIR / "sample"
OUTPUT_DIR = BASE_DIR / "output"
AUDIT_DIR = BASE_DIR / "audit"


# ---------------------------------------------------------------------------
# vLLM / LLM configuration (environment-driven)
# ---------------------------------------------------------------------------
#VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
#MODEL_NAME: str = os.getenv("VLLM_MODEL_NAME", "Qwen3-14B")
#VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "dummy")

# ---------------------------------------------------------------------------
# OpenRouter Rerank configuration (hardcoded)
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/rerank"
VLLM_BASE_URL=OPENROUTER_BASE_URL
OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
MODEL_NAME=OPENROUTER_MODEL

OPENROUTER_TOP_N = 3

# ---------------------------------------------------------------------------
# LibreOffice path (platform-aware)
# ---------------------------------------------------------------------------
LIBREOFFICE_CMD: str = os.getenv(
    "LIBREOFFICE_CMD",
    "soffice" if sys.platform == "win32" else "libreoffice",
)


# ---------------------------------------------------------------------------
# Helper: first existing path from a list of candidates
# ---------------------------------------------------------------------------
def first_existing_path(candidates: list[Path]) -> Path | None:
    """Return the first path that exists on disk, or None."""
    for p in candidates:
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Lazy bootstrap — call from main() only
# ---------------------------------------------------------------------------
INPUT_DIR: Path | None = None
NOTICE_TEMPLATE_PATH: Path | None = None
REPORT_TEMPLATE_PATH: Path | None = None


def init_config() -> None:
    """
    Bootstrap directories and auto-detect templates.

    Must be called once before using the pipeline. Factored out so that
    importing src.config does not trigger I/O or raise errors in contexts
    such as testing, documentation generation, or REPL exploration.
    """
    global INPUT_DIR, NOTICE_TEMPLATE_PATH, REPORT_TEMPLATE_PATH

    OUTPUT_DIR.mkdir(exist_ok=True)
    AUDIT_DIR.mkdir(exist_ok=True)

    # ---- Input directory auto-detection ----
    INPUT_DIR = first_existing_path([
        BASE_DIR / "Input",
        BASE_DIR / "input",
    ])

    if INPUT_DIR is None:
        available_items = sorted([p.name for p in BASE_DIR.iterdir()]) if BASE_DIR.exists() else []
        raise FileNotFoundError(
            f"No input directory found under {BASE_DIR}.\n"
            f"Tried: 'Input', 'input'\n"
            f"Available items in BASE_DIR: {available_items}"
        )

    # ---- Notice template auto-detection ----
    NOTICE_TEMPLATE_PATH = first_existing_path([
        SAMPLE_DIR / "Notice_Template.docx",
        SAMPLE_DIR / "notice.docx",
        SAMPLE_DIR / "Notice u.s 133(6).docx",
    ])

    if NOTICE_TEMPLATE_PATH is None:
        logger.warning(
            "No notice template found in %s — notice generation will be skipped. "
            "Tried: Notice_Template.docx, notice.docx, Notice u.s 133(6).docx",
            SAMPLE_DIR,
        )

    # ---- Report template auto-detection ----
    REPORT_TEMPLATE_PATH = first_existing_path([
        INPUT_DIR / "REPORT_TEMPLATE.docx",
        INPUT_DIR / "Report_Template.docx",
        INPUT_DIR / "report_template.docx",
        SAMPLE_DIR / "Tax_Investigation_Report_Template.docx",
        SAMPLE_DIR / "Tax_Investigation_Report.docx",
        SAMPLE_DIR / "REPORT_TEMPLATE.docx",
        SAMPLE_DIR / "report.docx",
    ])

    if REPORT_TEMPLATE_PATH is None:
        REPORT_TEMPLATE_PATH = NOTICE_TEMPLATE_PATH
