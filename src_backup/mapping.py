"""
Mapping module — converts raw extracted document data into canonical Pydantic models.

Includes multi-strategy identity extraction (structured JSON rows, vertical
key-value layout, blob parsing, and direct AIS file inspection via openpyxl).
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils import load_workbook
from src.models import (
    AISData,
    CanonicalTaxCase,
    Form16Data,
    ITRData,
    TaxpayerIdentity,
)
from src.case_discovery import CaseManifest, asdict
from src.parsing import (
    PAN_RE,
    clean_name,
    extract_identity_from_text,
    extract_name_from_text,
    extract_name_pan_ay_from_case_name,
    first_amount_after_keyword,
    flatten_text,
    normalize_assessment_year,
)

logger = logging.getLogger(__name__)

# Compiled AY regex (module-level for performance, consistent with PAN_RE/AMOUNT_RE)
_AY_BLOB_RE = re.compile(r"\b(\d{4}-\d{2,4})\b")


# ---------------------------------------------------------------------------
# Per-document canonical mapping
# ---------------------------------------------------------------------------
def map_form16_to_canonical(extracted: Dict[str, Any]) -> Form16Data:
    """Extract Form 16 fields from extracted text."""
    text = flatten_text(extracted)
    return Form16Data(
        employer_name=None,
        tan=None,
        gross_salary=first_amount_after_keyword(text, "gross salary"),
        tds_deducted=first_amount_after_keyword(text, "tds deducted"),
        chapter_via_deductions=first_amount_after_keyword(text, "chapter vi-a"),
    )


def map_ais_to_canonical(extracted: Dict[str, Any]) -> AISData:
    """Extract AIS fields from extracted text."""
    text = flatten_text(extracted)
    return AISData(
        salary=first_amount_after_keyword(text, "salary"),
        interest=first_amount_after_keyword(text, "interest"),
        dividend=first_amount_after_keyword(text, "dividend"),
        securities=first_amount_after_keyword(text, "securities"),
        tds=first_amount_after_keyword(text, "tds"),
        bank_deposits=first_amount_after_keyword(text, "deposit"),
    )


def map_itr_to_canonical(extracted: Dict[str, Any]) -> ITRData:
    """Extract ITR fields from extracted text."""
    text = flatten_text(extracted)
    return ITRData(
        salary=first_amount_after_keyword(text, "salary"),
        other_sources=first_amount_after_keyword(text, "other sources"),
        interest=first_amount_after_keyword(text, "interest"),
        dividend=first_amount_after_keyword(text, "dividend"),
        securities=first_amount_after_keyword(text, "securities"),
        tds=first_amount_after_keyword(text, "tds"),
        deductions=first_amount_after_keyword(text, "deduction"),
        total_income=first_amount_after_keyword(text, "total income"),
    )


# ---------------------------------------------------------------------------
# Normalised key name helper
# ---------------------------------------------------------------------------
def normalize_key_name(key: str) -> str:
    key = str(key).strip().lower()
    key = key.replace("_", " ").replace(".", " ").replace("-", " ")
    key = " ".join(key.split())
    return key


# ---------------------------------------------------------------------------
# Blob-based PAN / AY / Name extraction
# ---------------------------------------------------------------------------
def extract_pan_ay_name_from_blob(text: str):
    """Parse a free-text blob to find PAN, AY, and Name."""
    if not text:
        return None, None, None

    blob = str(text).replace("|", " ").replace("\t", " ")
    blob = re.sub(r"\s+", " ", blob).strip()

    pan = None
    ay = None
    name = None

    pan_match = PAN_RE.search(blob.upper())
    if pan_match:
        pan = pan_match.group(0).upper()

    ay_match = _AY_BLOB_RE.search(blob)
    if ay_match:
        ay = normalize_assessment_year(ay_match.group(1))

    # try to extract name between PAN and AY
    if pan and ay:
        try:
            start = blob.upper().find(pan)
            end = blob.find(ay, start + len(pan))
            if start != -1 and end != -1:
                candidate = blob[start + len(pan):end].strip(" -_:;/,.")
                candidate = clean_name(candidate)
                if candidate:
                    name = candidate
        except Exception:
            pass

    if not name:
        name = extract_name_from_text(blob)

    return name, pan, ay


# ---------------------------------------------------------------------------
# Vertical key-value layout
# ---------------------------------------------------------------------------
def extract_identity_from_vertical_kv_text(text: str):
    """
    Handle vertical KV layout::

        PAN            SHAMPE1234F
        Name           Sham
        AY             2025-26
        FY             2024-25
    """
    if not text:
        return None, None, None

    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    normalized = [normalize_key_name(x) for x in lines]

    expected_keys = ["pan", "name", "ay", "fy"]

    for i in range(len(normalized)):
        if normalized[i:i + 4] == expected_keys:
            values = lines[i + 4:i + 8]
            if len(values) >= 3:
                pan = None
                name = None
                ay = None

                pan_match = PAN_RE.search(values[0].upper())
                if pan_match:
                    pan = pan_match.group(0).upper()

                name = clean_name(values[1])
                ay = normalize_assessment_year(values[2])

                return name, pan, ay

    return None, None, None


# ---------------------------------------------------------------------------
# Structured document identity extraction
# ---------------------------------------------------------------------------
def extract_identity_from_structured_docs(
    extracted_docs: Dict[str, Dict[str, Any]],
    case_name: str = "",
) -> TaxpayerIdentity:
    """Iterate over extracted docs (ais, form16, itr) and extract identity."""
    found_name = None
    found_pan = None
    found_ay = None

    for source_key in ("ais", "form16", "itr"):
        extracted = extracted_docs.get(source_key, {})
        doc_json = extracted.get("docling_json", {}) or {}
        sheets = doc_json.get("sheets", {}) or {}
        raw_markdown = extracted.get("markdown", "") or ""

        # Pass 1: structured JSON rows
        for _sheet_name, records in sheets.items():
            if not isinstance(records, list):
                continue

            for row in records:
                if isinstance(row, dict):
                    normalized_row = {
                        normalize_key_name(k): ("" if v is None else str(v).strip())
                        for k, v in row.items()
                    }

                    pan_value = None
                    name_value = None
                    ay_value = None

                    for k, v in normalized_row.items():
                        if not pan_value and k in ("pan",):
                            m = PAN_RE.search(v.upper())
                            if m:
                                pan_value = m.group(0).upper()

                        if not name_value and k in (
                            "name", "assessee name", "taxpayer name", "employee name"
                        ):
                            cleaned = clean_name(v)
                            if cleaned:
                                name_value = cleaned

                        if not ay_value and k in ("ay", "a y", "assessment year", "asst year"):
                            normalized_ay = normalize_assessment_year(v)
                            if normalized_ay:
                                ay_value = normalized_ay

                    # blend fallback
                    if not (pan_value and ay_value):
                        blob = " ".join(str(v) for v in row.values())
                        b_name, b_pan, b_ay = extract_pan_ay_name_from_blob(blob)
                        name_value = name_value or b_name
                        pan_value = pan_value or b_pan
                        ay_value = ay_value or b_ay

                    if not found_pan and pan_value:
                        found_pan = pan_value
                    if not found_name and name_value:
                        found_name = name_value
                    if not found_ay and ay_value:
                        found_ay = ay_value

        # Pass 2: vertical key-value layout from markdown
        if raw_markdown:
            v_name, v_pan, v_ay = extract_identity_from_vertical_kv_text(raw_markdown)
            if not found_name and v_name:
                found_name = v_name
            if not found_pan and v_pan:
                found_pan = v_pan
            if not found_ay and v_ay:
                found_ay = v_ay

        # Pass 3: raw blob parsing
        if raw_markdown:
            b_name, b_pan, b_ay = extract_pan_ay_name_from_blob(raw_markdown)
            if not found_name and b_name:
                found_name = b_name
            if not found_pan and b_pan:
                found_pan = b_pan
            if not found_ay and b_ay:
                found_ay = b_ay

        if found_name and found_pan and found_ay:
            break

    fallback_name, fallback_pan, fallback_ay = extract_name_pan_ay_from_case_name(case_name or "")

    return TaxpayerIdentity(
        name=found_name or fallback_name,
        pan=found_pan or fallback_pan,
        assessment_year=found_ay or fallback_ay,
    )


# ---------------------------------------------------------------------------
# Direct AIS file extraction (openpyxl)
# ---------------------------------------------------------------------------
def extract_identity_from_ais_file(ais_file_path: Path) -> TaxpayerIdentity:
    """
    Read AIS.xlsx directly using openpyxl to extract PAN / Name / AY.

    Uses logger.info() so output can be controlled via logging level.
    """
    logger.info("=" * 60)
    logger.info("AIS extraction for file: %s", ais_file_path)
    logger.info("=" * 60)

    if load_workbook is None:
        logger.info("openpyxl not available — cannot read AIS Excel file")
        return TaxpayerIdentity(name=None, pan=None, assessment_year=None)

    if not ais_file_path.exists():
        logger.info("AIS file does not exist: %s", ais_file_path)
        return TaxpayerIdentity(name=None, pan=None, assessment_year=None)

    if ais_file_path.suffix.lower() not in (".xlsx", ".xlsm"):
        logger.info("Unsupported AIS file type: %s", ais_file_path.suffix)
        return TaxpayerIdentity(name=None, pan=None, assessment_year=None)

    try:
        wb = load_workbook(str(ais_file_path), data_only=True)
        logger.info("Workbook loaded. Sheets: %s", wb.sheetnames)
    except Exception as e:
        logger.warning("Failed to open workbook: %s", e)
        return TaxpayerIdentity(name=None, pan=None, assessment_year=None)

    found_name = None
    found_pan = None
    found_ay = None

    for ws in wb.worksheets:
        logger.info("Reading sheet: %s", ws.title)

        flat_values = []
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is not None and str(cell).strip():
                    flat_values.append(str(cell).strip())

        logger.debug("Flattened values: %s", flat_values[:10])

        if not flat_values:
            logger.debug("No usable values in sheet '%s'", ws.title)
            continue

        norm = [normalize_key_name(v) for v in flat_values]

        # Exact vertical pattern: PAN, Name, AY, FY, <PAN>, <Name>, <AY>, <FY>
        for i in range(len(norm)):
            if norm[i:i + 4] == ["pan", "name", "ay", "fy"]:
                vals = flat_values[i + 4:i + 8]
                logger.info("Vertical PAN/Name/AY/FY pattern found: %s", vals)

                if len(vals) >= 3:
                    pan = None
                    name = None
                    ay = None

                    m = PAN_RE.search(vals[0].upper())
                    if m:
                        pan = m.group(0).upper()

                    name = clean_name(vals[1])
                    ay = normalize_assessment_year(vals[2])

                    logger.info("Extracted -> PAN: %s, Name: %s, AY: %s", pan, name, ay)

                    if pan or name or ay:
                        logger.info("[OK] Extraction successful from vertical AIS pattern")
                        return TaxpayerIdentity(
                            name=name,
                            pan=pan,
                            assessment_year=ay,
                        )

        # Fallback: parse whole sheet as one blob
        blob = " ".join(flat_values)
        logger.debug("Blob fallback: %s...", blob[:100])

        b_name, b_pan, b_ay = extract_pan_ay_name_from_blob(blob)
        logger.debug("Blob -> PAN: %s, Name: %s, AY: %s", b_pan, b_name, b_ay)

        if b_name:
            found_name = b_name
        if b_pan:
            found_pan = b_pan
        if b_ay:
            found_ay = b_ay

        if found_name and found_pan and found_ay:
            logger.info("[OK] Extraction successful from blob fallback")
            break

    logger.info("Final identity — PAN: %s, Name: %s, AY: %s", found_pan, found_name, found_ay)

    if not any([found_pan, found_name, found_ay]):
        logger.info("[FAIL] No identity fields could be extracted from AIS file.")
    else:
        logger.info("[OK] AIS extraction completed with at least partial data.")

    return TaxpayerIdentity(
        name=found_name,
        pan=found_pan,
        assessment_year=found_ay,
    )


# ---------------------------------------------------------------------------
# Canonical case builder
# ---------------------------------------------------------------------------
def build_canonical_case(
    manifest: CaseManifest,
    extracted_docs: Dict[str, Dict[str, Any]],
) -> CanonicalTaxCase:
    """
    Build a :class:`CanonicalTaxCase` from a case manifest and its extracted documents.

    Identity is resolved by merging results from three strategies:
    1. Combined free-text extraction
    2. Structured document JSON/markdown
    3. Direct AIS file inspection (openpyxl)
    """
    combined_text = "\n".join(
        flatten_text(extracted_docs[k]) for k in ("form16", "ais", "itr")
    )

    # 1. text-based extraction
    text_identity = extract_identity_from_text(combined_text, manifest.case_name)

    # 2. extracted structured docs
    structured_identity = extract_identity_from_structured_docs(
        extracted_docs, manifest.case_name
    )

    # 3. direct AIS source-file extraction
    ais_file_identity = extract_identity_from_ais_file(
        Path(manifest.files["ais"])
    )

    # 4. merge in priority order
    identity = TaxpayerIdentity(
        name=text_identity.name or structured_identity.name or ais_file_identity.name,
        pan=text_identity.pan or structured_identity.pan or ais_file_identity.pan,
        assessment_year=(
            text_identity.assessment_year
            or structured_identity.assessment_year
            or ais_file_identity.assessment_year
        ),
    )

    provenance = {
        "manifest": asdict(manifest),
        "source_docs": {
            k: {
                "file_name": v["file_name"],
                "source_path": v["source_path"],
                "extracted_at": v["extracted_at"],
                "extraction_method": v.get("extraction_method", "unknown"),
            }
            for k, v in extracted_docs.items()
        },
        "identity_debug": {
            "text_identity": text_identity.model_dump() if text_identity else {},
            "structured_identity": structured_identity.model_dump() if structured_identity else {},
            "ais_file_identity": ais_file_identity.model_dump() if ais_file_identity else {},
            "final_identity": identity.model_dump() if identity else {},
        },
    }

    return CanonicalTaxCase(
        case_id=manifest.case_id,
        identity=identity,
        form16=map_form16_to_canonical(extracted_docs["form16"]),
        ais=map_ais_to_canonical(extracted_docs["ais"]),
        itr=map_itr_to_canonical(extracted_docs["itr"]),
        provenance=provenance,
    )
