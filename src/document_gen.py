"""
Template-based document generation — produces DOCX reports and notices from
Jinja2-style ``.docx`` templates or plain-text ``.txt`` templates.

Also supports DOCX → PDF conversion via LibreOffice (headless).
"""

import json
import logging
import subprocess
import sys  # platform detection (win32/linux/darwin)
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils import DocxTemplate, Document, ensure_dir, now_iso

logger = logging.getLogger(__name__)

try:
    from fpdf.enums import XPos
except ImportError:
    XPos = None
from src.models import CanonicalTaxCase
from src.discrepancies import Discrepancy, asdict
from src.decision import DecisionResult
from src.paths import LIBREOFFICE_CMD


# ---------------------------------------------------------------------------
# Default notice context
# ---------------------------------------------------------------------------
def _format_discrepancies_block(discrepancies: List[Dict[str, Any]]) -> str:
    """Format discrepancy list as a human-readable text block for templates."""
    if not discrepancies:
        return "No discrepancies detected."
    lines = []
    for i, d in enumerate(discrepancies, start=1):
        lines.append(f"{i}. Category: {d.get('category', '')}")
        lines.append(f"   Source Reported Value: {d.get('source_reported_value', '')}")
        lines.append(f"   Declared Value: {d.get('declared_value', '')}")
        lines.append(f"   Delta: {d.get('delta', '')}")
        lines.append(f"   Materiality: {d.get('materiality', '')}")
        lines.append(f"   Severity: {d.get('severity', '')}")
        lines.append(f"   Reason: {d.get('reason', '')}")
        lines.append("")
    return "\n".join(lines)


def _derive_financial_year(assessment_year: Optional[str]) -> str:
    """Derive financial year from assessment year (AY 2025-26 → FY 2024-25)."""
    if not assessment_year:
        return "NA"
    import re
    m = re.match(r"(\d{4})", assessment_year)
    if m:
        fy_start = int(m.group(1)) - 1
        return f"{fy_start}-{str(fy_start + 1)[-2:]}"
    return assessment_year


def default_notice_context(
    case: CanonicalTaxCase,
    discrepancies: List[Discrepancy],
    decision: DecisionResult,
) -> Dict[str, Any]:
    """Build the Jinja2 template context for report/notice generation."""
    display_name = case.identity.name or "Unknown_User"
    display_pan = case.identity.pan or "NOPAN"
    display_ay = case.identity.assessment_year or "NOAY"

    business_case_id = f"{display_name}_{display_pan}_{display_ay}"
    disc_dicts = [asdict(d) for d in discrepancies]

    return {
        "case_id": business_case_id,
        "assessee_name": case.identity.name or "NA",
        "pan": case.identity.pan or "NA",
        "assessment_year": case.identity.assessment_year or "NA",
        "financial_year": _derive_financial_year(case.identity.assessment_year),
        "decision_type": decision.decision_type,
        "reason_codes": "\n".join(decision.reason_codes),
        "discrepancies": disc_dicts,
        # discrepancies_block is a pre-formatted text block used by both
        # .txt templates (via simple_text_render) and .docx templates (via docxtpl)
        "discrepancies_block": _format_discrepancies_block(disc_dicts),
        "generated_at": now_iso(),
    }


# ---------------------------------------------------------------------------
# Plain-text template rendering
# ---------------------------------------------------------------------------
def simple_text_render(template_text: str, context: Dict[str, Any]) -> str:
    """
    Replace ``{{ placeholder }}`` tokens in a plain-text template.

    Supports placeholders:
      ``{{ case_id }}``, ``{{ assessee_name }}``, ``{{ pan }}``,
      ``{{ assessment_year }}``, ``{{ decision_type }}``,
      ``{{ reason_codes }}``, ``{{ generated_at }}``,
      ``{{ discrepancies_block }}``
    """
    rendered = template_text

    flat_context = {
        "case_id": context.get("case_id", ""),
        "assessee_name": context.get("assessee_name", ""),
        "pan": context.get("pan", ""),
        "assessment_year": context.get("assessment_year", ""),
        "decision_type": context.get("decision_type", ""),
        "reason_codes": context.get("reason_codes", ""),
        "generated_at": context.get("generated_at", ""),
    }

    for k, v in flat_context.items():
        rendered = rendered.replace(f"{{{{ {k} }}}}", str(v))
        rendered = rendered.replace(f"{{{{{k}}}}}", str(v))

    # Use the pre-formatted discrepancies_block from context (set by
    # default_notice_context), falling back to inline formatting for safety
    disc_block = context.get(
        "discrepancies_block",
        _format_discrepancies_block(context.get("discrepancies", [])),
    )
    rendered = rendered.replace("{{ discrepancies_block }}", disc_block)

    return rendered


# ---------------------------------------------------------------------------
# TXT → DOCX renderer
# ---------------------------------------------------------------------------
def render_txt_to_docx(
    template_path: Path,
    output_path: Path,
    context: Dict[str, Any],
) -> None:
    """Render a TXT template into a DOCX file via python-docx."""
    if Document is None:
        raise ImportError(
            "python-docx is not installed. "
            "Install python-docx to generate DOCX from TXT template."
        )

    template_text = template_path.read_text(encoding="utf-8")
    rendered_text = simple_text_render(template_text, context)

    doc = Document()
    for line in rendered_text.splitlines():
        doc.add_paragraph(line)

    doc.save(str(output_path))


# ---------------------------------------------------------------------------
# Main DOCX template renderer
# ---------------------------------------------------------------------------
def render_docx_template(
    template_path: Path,
    output_path: Path,
    context: Dict[str, Any],
) -> None:
    """
    Render a template (``.docx`` or ``.txt``) against *context* and save to
    *output_path*.

    - ``.txt`` templates: rendered via placeholder replacement → python-docx
    - ``.docx`` templates: rendered via ``docxtpl`` (Jinja2 tags)
    """
    suffix = template_path.suffix.lower()

    if suffix == ".txt":
        render_txt_to_docx(template_path, output_path, context)
        return

    if suffix == ".docx":
        if DocxTemplate is None:
            json_fallback = output_path.with_suffix(".json")
            with open(json_fallback, "w", encoding="utf-8") as f:
                json.dump(
                    {"template_path": str(template_path), "context": context},
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            return

        doc = DocxTemplate(str(template_path))
        doc.render(context)
        doc.save(str(output_path))
        return

    raise ValueError(
        f"Unsupported template format: {template_path.name}. Use .docx or .txt"
    )


# ---------------------------------------------------------------------------
# DOCX → PDF conversion (LibreOffice)
# ---------------------------------------------------------------------------
def _find_or_download_unicode_font(pdf: Any) -> Optional[str]:
    """
    Find a Unicode-capable TTF font on the system or download DejaVuSans as fallback.

    Returns the font name registered with *pdf*, or None if only built-in fonts work.
    """
    # ── 1. Search for system fonts across platforms ──
    # Platform-specific system font paths.
    # NOTE: fpdf2's add_font() only supports single .ttf files, not .ttc
    #       (TrueType Collections). Helvetica.ttc entries are excluded.
    font_candidates = [
        # -- Windows --
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        # -- Linux (Debian/Ubuntu/Fedora/Arch) --
        r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        r"/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        r"/usr/share/fonts/TTF/DejaVuSans.ttf",
        r"/usr/share/fonts/dejavu/DejaVuSans.ttf",
        # -- NixOS --
        r"/run/current-system/sw/share/fonts/dejavu/DejaVuSans.ttf",
        # -- macOS (Intel via Homebrew) --
        r"/usr/local/share/fonts/dejavu/DejaVuSans.ttf",
        # -- macOS (Apple Silicon via Homebrew) --
        r"/opt/homebrew/share/fonts/dejavu/DejaVuSans.ttf",
        # -- macOS (stock system fonts — all .ttf compatible) --
        r"/Library/Fonts/Arial.ttf",
        r"/System/Library/Fonts/Supplemental/Arial.ttf",
    ]

    for font_path in font_candidates:
        if Path(font_path).exists():
            try:
                pdf.add_font("UnicodeFont", "", font_path, uni=True)
                try:
                    pdf.add_font("UnicodeFont", "B", font_path, uni=True)
                except Exception:
                    pass
                logger.info("Loaded system font: %s", font_path)
                return "UnicodeFont"
            except Exception as e:
                logger.debug("Font load failed %s: %s", font_path, e)
                continue

    # ── 2. Download DejaVuSans (open source / public domain) ──
    font_dir = Path.home() / ".tax_investigation" / "fonts"
    from src.utils import ensure_dir
    ensure_dir(font_dir)
    dejavu_path = font_dir / "DejaVuSans.ttf"

    if not dejavu_path.exists():
        import urllib.request
        DEJAVU_URL = (
            "https://raw.githubusercontent.com/dejavu-fonts"
            "/dejavu-fonts/master/ttf/DejaVuSans.ttf"
        )
        try:
            logger.info("Downloading DejaVuSans font for PDF rendering...")
            urllib.request.urlretrieve(DEJAVU_URL, str(dejavu_path))
            logger.info("DejaVuSans downloaded to %s", dejavu_path)
        except Exception as e:
            logger.debug("Font download failed: %s", e)
            return None

    if dejavu_path.exists():
        try:
            pdf.add_font("UnicodeFont", "", str(dejavu_path), uni=True)
            try:
                pdf.add_font("UnicodeFont", "B", str(dejavu_path), uni=True)
            except Exception:
                pass
            logger.info("Loaded DejaVuSans from %s", dejavu_path)
            return "UnicodeFont"
        except Exception as e:
            logger.debug("DejaVuSans load failed: %s", e)

    return None


def _convert_docx_to_pdf_via_fpdf(docx_path: Path, pdf_path: Path) -> bool:
    """
    Fallback: render DOCX content to PDF using fpdf2 (pure Python).

    This is a fully self-contained Python PDF generator that works on any
    system without requiring LibreOffice, Microsoft Word, or any other
    system tool. It auto-discovers or downloads Unicode fonts.
    
    Enhanced to preserve: paragraphs, tables, lists, headers, Unicode.
    """
    try:
        from fpdf import FPDF

        doc = Document(str(docx_path))
        pdf = FPDF(unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)

        # Find or download a Unicode font for Indian tax chars (₹, etc.)
        unicode_font = _find_or_download_unicode_font(pdf)

        pdf.add_page()

        # Process all document elements in order using XML for full fidelity
        for element in doc.element.body:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            if tag == 'p':  # Paragraph
                _render_paragraph_fpdf(pdf, element, unicode_font)
            
            elif tag == 'tbl':  # Table
                _render_table_fpdf(pdf, element, unicode_font)
        
        pdf.output(str(pdf_path))
        return pdf_path.exists()
    except Exception as e:
        logger.debug("fpdf2 conversion failed: %s", e)
        return False


def _render_paragraph_fpdf(pdf, para_element, unicode_font):
    """Render a paragraph with full formatting from XML element."""
    try:
        from lxml import etree
        
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # Reset x position to left margin before each paragraph
        pdf.x = pdf.l_margin
        
        # Extract text with formatting
        runs = para_element.findall('.//w:r', namespaces=ns)
        if not runs:
            # Simple paragraph without runs
            text = ''.join(para_element.itertext()).strip()
            if text:
                _write_text(pdf, text, unicode_font, bold=False, size=9)
            return
        
        # Check if paragraph is a header
        is_header = all(r.find('.//w:b', namespaces=ns) is not None for r in runs if any(t.text for t in r.findall('.//w:t', namespaces=ns)))
        full_text_parts = []
        for r in runs:
            t_elem = r.find('.//w:t', namespaces=ns)
            if t_elem is not None and t_elem.text:
                full_text_parts.append(t_elem.text)
        full_text = ''.join(full_text_parts)
        full_text = full_text.strip()
        
        if not full_text:
            return
            
        font_name = unicode_font or "Helvetica"
        if is_header:
            pdf.set_font(font_name, "B", 11)
        else:
            pdf.set_font(font_name, "", 9)
        
        # Write with proper wrapping and reset x to left margin after
        usable_w = pdf.w - 2 * pdf.l_margin
        pdf.multi_cell(usable_w, 4.5, full_text, new_x=XPos.LMARGIN)
        
    except Exception as e:
        logger.debug("Paragraph rendering failed: %s", e)
        # Fallback to simple text extraction
        pdf.x = pdf.l_margin
        text = ''.join(para_element.itertext()).strip()
        if text:
            _write_text(pdf, text, unicode_font, bold=False, size=9)


def _write_text(pdf, text, unicode_font, bold=False, size=9):
    """Helper to write text with proper font and encoding."""
    pdf.x = pdf.l_margin
    font_name = unicode_font or "Helvetica"
    style = "B" if bold else ""
    pdf.set_font(font_name, style, size)
    
    if unicode_font:
        clean_text = text
    else:
        clean_text = text.encode("ascii", "replace").decode("ascii")
        if not clean_text.strip():
            clean_text = text
    
    usable_w = pdf.w - 2 * pdf.l_margin
    pdf.multi_cell(usable_w, 4.5, clean_text, new_x=XPos.LMARGIN if XPos else None)


def _render_table_fpdf(pdf, tbl_element, unicode_font):
    """Render a table from DOCX XML element with full content."""
    try:
        from lxml import etree
        
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        font_name = unicode_font or "Helvetica"
        pdf.set_font(font_name, "", 8)
        
        # Get table rows
        rows = tbl_element.findall('.//w:tr', namespaces=ns)
        if not rows:
            return
            
        # Calculate column widths based on content
        all_cells_per_row = []
        max_cols = 0
        for row in rows:
            cells = row.findall('.//w:tc', namespaces=ns)
            all_cells_per_row.append(cells)
            max_cols = max(max_cols, len(cells))
        
        if max_cols == 0:
            return
            
        # Dynamic column width based on page width
        page_width = pdf.w - 2 * pdf.l_margin
        col_width = page_width / max_cols
        
        for cells in all_cells_per_row:
            # Check page break
            if pdf.get_y() + 8 > pdf.h - pdf.b_margin:
                pdf.add_page()
            
            x_start = pdf.get_x()
            row_height = 7
            
            for i, cell in enumerate(cells):
                # Get cell text with formatting
                cell_text = ''.join(cell.itertext()).strip()
                # Truncate if too long for cell
                max_chars = max(1, int(col_width / 1.8))  # approximate
                if len(cell_text) > max_chars:
                    cell_text = cell_text[:max_chars-3] + "..."
                
                x = x_start + i * col_width
                pdf.set_xy(x, pdf.get_y())
                pdf.cell(col_width, row_height, cell_text, border=1, align='L')
            
            # Handle remaining columns if row has fewer cells
            for i in range(len(cells), max_cols):
                x = x_start + i * col_width
                pdf.set_xy(x, pdf.get_y())
                pdf.cell(col_width, row_height, "", border=1)
            
            pdf.ln(row_height)
            
    except Exception as e:
        logger.debug("Table rendering failed: %s", e)
        
        font_name = unicode_font or "Helvetica"
        pdf.set_font(font_name, "", 8)
        
        # Get table rows
        rows = tbl_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr')
        if not rows:
            return
            
        # Calculate column widths
        num_cols = max(len(row.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc')) for row in rows)
        col_width = (pdf.w - 2 * pdf.l_margin) / max(num_cols, 1)
        
        for row in rows:
            cells = row.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc')
            row_height = 6
            
            # Check if we need a page break
            if pdf.get_y() + row_height > pdf.h - pdf.b_margin:
                pdf.add_page()
            
            x_start = pdf.get_x()
            for i, cell in enumerate(cells):
                cell_text = ''.join(cell.itertext()).strip()
                x = x_start + i * col_width
                pdf.set_xy(x, pdf.get_y())
                pdf.cell(col_width, row_height, cell_text[:50], border=1)
            
            pdf.ln(row_height)
            
    except Exception as e:
        logger.debug("Table rendering failed: %s", e)


def convert_docx_to_pdf(docx_path: Path, outdir: Path, timeout_seconds: int = 120) -> Path:
    """
    Convert a DOCX file to PDF.

    Tries (in order):
    1. LibreOffice (headless) — best quality, cross-platform.
    2. docx2pdf (Microsoft Word COM on Windows) — Windows native.
    3. fpdf2 (pure Python) — always available fallback.

    Raises RuntimeError if all methods fail.
    """
    ensure_dir(outdir)
    pdf_path = outdir / f"{docx_path.stem}.pdf"

    # ---- Method 1: LibreOffice ----
    try:
        cmd = [
            LIBREOFFICE_CMD,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(outdir),
            str(docx_path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds
        )
        if result.returncode == 0 and pdf_path.exists():
            logger.info("[OK] PDF generated via LibreOffice")
            return pdf_path
        logger.debug("LibreOffice exit code %s: %s", result.returncode, result.stderr)
    except Exception as e:
        logger.debug("LibreOffice conversion failed: %s", e)

    # ---- Method 2: docx2pdf (Windows COM — skip on Linux/macOS) ----
    if sys.platform == "win32":
        try:
            from docx2pdf import convert as docx2pdf_convert
            docx2pdf_convert(str(docx_path), str(outdir))
            if pdf_path.exists():
                logger.info("[OK] PDF generated via docx2pdf")
                return pdf_path
        except Exception as e:
            logger.debug("docx2pdf conversion failed: %s", e)

    # ---- Method 3: fpdf2 (pure Python — always works) ----
    if _convert_docx_to_pdf_via_fpdf(docx_path, pdf_path):
        logger.info("[OK] PDF generated via fpdf2")
        return pdf_path

    raise RuntimeError(
        f"Could not convert {docx_path.name} to PDF. "
        f"Install LibreOffice (preferred) or ensure Microsoft Word is available "
        f"for docx2pdf fallback."
    )
