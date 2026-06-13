"""
Document extraction module.

Attempts to extract text and structured content from DOCX and XLSX files
using the *docling* library when available, with multiple fallback strategies.
"""

import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import xml.etree.ElementTree as ET

from src.utils import Document, DocumentConverter, now_iso

logger = logging.getLogger(__name__)

# (DocumentConverter is imported from src.utils — gracefully None if docling is missing)


# ---------------------------------------------------------------------------
# DOCX fallback (python-docx → raw XML)
# ---------------------------------------------------------------------------
def read_docx_fallback(file_path: Path) -> Dict[str, Any]:
    """Extract text from a DOCX file using python-docx, then raw XML as fallback."""
    text_parts = []

    # try python-docx first
    try:
        if Document is None:
            raise ImportError("python-docx not installed")

        doc = Document(str(file_path))
        for p in doc.paragraphs:
            if p.text and p.text.strip():
                text_parts.append(p.text.strip())

        for table in doc.tables:
            for row in table.rows:
                vals = [cell.text.strip() for cell in row.cells]
                if any(vals):
                    text_parts.append(" | ".join(vals))

        text = "\n".join(text_parts)
        return {
            "file_name": file_path.name,
            "source_path": str(file_path),
            "extracted_at": now_iso(),
            "docling_json": {"raw_text": text},
            "markdown": text,
            "extraction_method": "python-docx",
        }
    except Exception as e:
        logger.debug("python-docx failed for %s: %s — trying zip fallback", file_path.name, e)

    # raw zip/xml fallback
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            xml_content = z.read("word/document.xml")

        root = ET.fromstring(xml_content)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        texts = []
        for node in root.iterfind(".//w:t", ns):
            if node.text:
                texts.append(node.text)

        text = "\n".join(texts)
        return {
            "file_name": file_path.name,
            "source_path": str(file_path),
            "extracted_at": now_iso(),
            "docling_json": {"raw_text": text},
            "markdown": text,
            "extraction_method": "docx-zip-fallback",
        }
    except Exception as e:
        raise RuntimeError(f"Unable to read DOCX file {file_path.name}: {e}")


# ---------------------------------------------------------------------------
# XLSX fallback (pandas)
# ---------------------------------------------------------------------------
def read_xlsx_fallback(file_path: Path) -> Dict[str, Any]:
    """Extract all sheets from an XLSX file via pandas/openpyxl."""
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    sheets_json = {}
    sheet_text_blocks = []

    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet, engine="openpyxl")
        df = df.fillna("")

        records = df.astype(str).to_dict(orient="records")
        sheets_json[sheet] = records

        block_lines = [f"# Sheet: {sheet}"]
        if not df.empty:
            headers = [str(c) for c in df.columns]
            block_lines.append(" | ".join(headers))
            for _, row in df.astype(str).iterrows():
                block_lines.append(" | ".join(row.tolist()))

        sheet_text_blocks.append("\n".join(block_lines))

    markdown = "\n\n".join(sheet_text_blocks)

    return {
        "file_name": file_path.name,
        "source_path": str(file_path),
        "extracted_at": now_iso(),
        "docling_json": {"sheets": sheets_json},
        "markdown": markdown,
        "extraction_method": "pandas-excel",
    }


# ---------------------------------------------------------------------------
# Main extraction dispatcher
# ---------------------------------------------------------------------------
def extract_with_docling(file_path: Path) -> Dict[str, Any]:
    """
    Extract content from *file_path*.

    Uses *docling* for DOCX (with JSON/markdown export). Falls back to
    python-docx / raw XML for DOCX and pandas for XLSX.
    """
    suffix = file_path.suffix.lower()

    # XLSX → pandas-direct
    if suffix in (".xlsx", ".xls"):
        return read_xlsx_fallback(file_path)

    # Use docling if available
    if DocumentConverter is not None:
        try:
            converter = DocumentConverter()
            result = converter.convert(str(file_path))
            doc = result.document

            export_json = None
            export_markdown = None
            try:
                export_json = doc.export_to_dict()
            except Exception:
                try:
                    export_json = json.loads(doc.export_to_json())
                except Exception:
                    export_json = {"raw": str(doc)}

            try:
                export_markdown = doc.export_to_markdown()
            except Exception:
                export_markdown = None

            return {
                "file_name": file_path.name,
                "source_path": str(file_path),
                "extracted_at": now_iso(),
                "docling_json": export_json,
                "markdown": export_markdown,
                "extraction_method": "docling",
            }
        except Exception as e:
            logger.debug("Docling failed for %s: %s — trying docx fallback", file_path.name, e)

    # DOCX fallback when docling is not installed or fails
    if suffix == ".docx":
        return read_docx_fallback(file_path)

    # Plain-text fallback
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return {
            "file_name": file_path.name,
            "source_path": str(file_path),
            "extracted_at": now_iso(),
            "docling_json": {"raw_text": text},
            "markdown": text,
            "extraction_method": "text-fallback",
        }
    except Exception as e:
        raise RuntimeError(
            f"Unsupported file format or unreadable file: {file_path.name} ({e})"
        )
