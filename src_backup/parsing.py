"""
Text and table parsing helpers for tax document content.

Provides regex-based extraction of PAN, assessment year, taxpayer names,
and numerical amounts from both free text and table-structured data.
"""

import json
import re
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils import safe_decimal
from src.models import TaxpayerIdentity


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------
AMOUNT_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{2,3})*|\d+)(?:\.\d+)?(?!\d)")
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I)

# Assessment Year patterns (multi-format)
AY_PATTERNS = [
    re.compile(r"\bAY\s*[\-:]?\s*(\d{4}\s*-\s*\d{2,4})\b", re.I),
    re.compile(r"\bA\.?Y\.?\s*[\-:]?\s*(\d{4}\s*-\s*\d{2,4})\b", re.I),
    re.compile(r"\bAssessment\s*Year\s*[\-:]?\s*(\d{4}\s*-\s*\d{2,4})\b", re.I),
    re.compile(r"\bAsst\.?\s*Year\s*[\-:]?\s*(\d{4}\s*-\s*\d{2,4})\b", re.I),
]

# Name patterns (labelled)
NAME_PATTERNS = [
    re.compile(r"\bAssessee\s*Name\s*[\-:]\s*([A-Za-z][A-Za-z .&/-]{2,100})", re.I),
    re.compile(r"\bTaxpayer\s*Name\s*[\-:]\s*([A-Za-z][A-Za-z .&/-]{2,100})", re.I),
    re.compile(r"\bEmployee\s*Name\s*[\-:]\s*([A-Za-z][A-Za-z .&/-]{2,100})", re.I),
    re.compile(r"\bName\s*[\-:]\s*([A-Za-z][A-Za-z .&/-]{2,100})", re.I),
]


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def normalize_assessment_year(value: Optional[str]) -> Optional[str]:
    """Normalise AY string to ``YYYY-YY`` format."""
    if not value:
        return None

    s = str(value).strip().replace("–", "-").replace("—", "-").replace(" ", "")
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    m = re.match(r"^(\d{4})-(\d{4})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)[-2:]}"  # 2025-2026 → 2025-26

    return s


def clean_name(name: Optional[str]) -> Optional[str]:
    """Sanitise a taxpayer name string."""
    if not name:
        return None

    s = str(name).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^A-Za-z .&/-]", "", s).strip()

    if len(s) < 2:
        return None

    blocked = {"assessment year", "case id", "pan", "name", "ay", "fy"}
    if s.lower() in blocked:
        return None

    return s


# ---------------------------------------------------------------------------
# Text flattening
# ---------------------------------------------------------------------------
def flatten_text(extracted: Dict[str, Any]) -> str:
    """Return markdown text or JSON dump from an extraction result."""
    md = extracted.get("markdown")
    if md:
        return md
    return json.dumps(extracted.get("docling_json", {}), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Amount extraction
# ---------------------------------------------------------------------------
def first_amount_after_keyword(
    text: str,
    keyword: str,
    default: Decimal = Decimal("0"),
) -> Decimal:
    """Find the first numeric amount appearing after *keyword* in *text*."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return default

    segment = text[idx: idx + 300]
    m = AMOUNT_RE.search(segment)
    return safe_decimal(m.group(0), default) if m else default


# ---------------------------------------------------------------------------
# Identity extraction helpers
# ---------------------------------------------------------------------------
def extract_name_from_text(text: str) -> Optional[str]:
    """Extract a taxpayer name from labelled fields."""
    if not text:
        return None

    for pattern in NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = clean_name(m.group(1))
            if candidate:
                return candidate

    return None


def extract_assessment_year_from_text(text: str) -> Optional[str]:
    """Extract an assessment year using any of the known formats."""
    if not text:
        return None

    for pattern in AY_PATTERNS:
        m = pattern.search(text)
        if m:
            return normalize_assessment_year(m.group(1))

    return None


# ---------------------------------------------------------------------------
# Table-aware identity extraction
# ---------------------------------------------------------------------------
def extract_identity_from_table_text(text: str):
    """
    Handle table-like extracted rows::

        PAN | Name | AY | FY
        SHAMPE1234F | Sham | 2025-26 | 2024-25
    """
    if not text:
        return None, None, None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    split_lines = [re.split(r"\s*\|\s*|\t+", line) for line in lines]

    for i in range(len(split_lines) - 1):
        header = [h.strip().lower() for h in split_lines[i]]
        row = [r.strip() for r in split_lines[i + 1]]

        if len(header) < 2 or len(row) < 2:
            continue

        header_map = {col: idx for idx, col in enumerate(header)}

        pan_idx = None
        name_idx = None
        ay_idx = None

        for key in header_map:
            if key in ("pan",):
                pan_idx = header_map[key]
            elif key in ("name", "assessee name", "taxpayer name", "employee name"):
                name_idx = header_map[key]
            elif key in ("ay", "a.y.", "assessment year", "asst year"):
                ay_idx = header_map[key]

        if pan_idx is None and name_idx is None and ay_idx is None:
            continue

        pan = None
        name = None
        ay = None

        if pan_idx is not None and pan_idx < len(row):
            pan_candidate = row[pan_idx].strip().upper()
            m = PAN_RE.search(pan_candidate)
            if m:
                pan = m.group(0).upper()

        if name_idx is not None and name_idx < len(row):
            name = clean_name(row[name_idx])

        if ay_idx is not None and ay_idx < len(row):
            ay = normalize_assessment_year(row[ay_idx])

        if pan or name or ay:
            return name, pan, ay

    return None, None, None


def extract_name_pan_ay_from_case_name(case_name: str):
    """
    Parse case folder name pattern::

        Rahul_Sharma_ABCPE1234F_2025-26
    """
    if not case_name:
        return None, None, None

    pan_match = PAN_RE.search(case_name)
    pan = pan_match.group(0).upper() if pan_match else None

    ay = None
    m = re.search(r"(\d{4}-\d{2,4})", case_name)
    if m:
        ay = normalize_assessment_year(m.group(1))

    name = case_name
    if pan:
        name = name.replace(pan, "")
    if ay:
        name = name.replace(ay, "")

    name = name.replace("_", " ").replace("-", " ").strip()
    name = clean_name(name)

    return name, pan, ay


# ---------------------------------------------------------------------------
# Combined identity extraction
# ---------------------------------------------------------------------------
def extract_identity_from_text(text: str, case_name: Optional[str] = None) -> TaxpayerIdentity:
    """
    Extract taxpayer identity by combining free-text, table, and case-name fallback.
    """
    text = text or ""

    # 1. From free text / labels
    pan = None
    pan_match = PAN_RE.search(text)
    if pan_match:
        pan = pan_match.group(0).upper()

    ay = extract_assessment_year_from_text(text)
    name = extract_name_from_text(text)

    # 2. From table-like rows
    table_name, table_pan, table_ay = extract_identity_from_table_text(text)

    if not name and table_name:
        name = table_name
    if not pan and table_pan:
        pan = table_pan
    if not ay and table_ay:
        ay = table_ay

    # 3. Fallback from case folder name
    fallback_name, fallback_pan, fallback_ay = extract_name_pan_ay_from_case_name(case_name or "")

    if not name:
        name = fallback_name
    if not pan:
        pan = fallback_pan
    if not ay:
        ay = fallback_ay

    return TaxpayerIdentity(
        name=name,
        pan=pan,
        assessment_year=ay,
    )
