"""
Tax Investigation System — Main Entry Point

Orchestrates the full pipeline:
  1. Case discovery (single or batch)
  2. Document extraction
  3. Canonical case building (identity + financial data)
  4. Validation & normalisation
  5. Deterministic discrepancy analysis
  6. LLM-based analytical review (with deterministic fallback)
  7. Decision composition
  8. Report generation (DOCX / PDF)
  9. Notice generation (if required)
  10. Output packaging (JSON audit trail)

Usage:
    python main.py                          # Process all discovered cases
    python main.py --case CASE_001          # Process a single case by ID
    python main.py --dry-run                # List cases without processing
"""

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging so all module-level logger calls produce visible output
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)

from src.config import init_config
from src.utils import ensure_dir, now_iso
from src.case_discovery import CaseManifest, discover_cases
from src.extraction import extract_with_docling
from src.mapping import build_canonical_case
from src.validation import validate_tax_case
from src.discrepancies import Discrepancy, reconcile_case
from src.llm_reviewer import run_vllm_review
from src.decision import DecisionResult, compose_decision
from src.document_gen import (
    default_notice_context,
    render_docx_template,
    convert_docx_to_pdf,
)
from src.output import write_json, package_case_outputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sanitize_for_path(value: str) -> str:
    """Remove/replace characters unsafe for file/folder names."""
    value = (value or "").strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "Unknown"


def build_output_folder_name(
    manifest: CaseManifest,
    canonical_case: Any,  # CanonicalTaxCase (avoid circular import at top)
) -> str:
    """Create a human-readable output folder name."""
    from src.models import CanonicalTaxCase

    case = canonical_case  # type: CanonicalTaxCase
    user_name = case.identity.name or manifest.case_name or "UnknownUser"
    pan = case.identity.pan or "NOPAN"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_user_name = sanitize_for_path(user_name)
    safe_pan = sanitize_for_path(pan)

    return f"{safe_user_name}_{safe_pan}_{timestamp}"


def extract_case_documents(manifest: CaseManifest) -> Dict[str, Dict[str, Any]]:
    """Extract all documents referenced in the manifest."""
    return {
        role: extract_with_docling(Path(path))
        for role, path in manifest.files.items()
    }


# ---------------------------------------------------------------------------
# Single-case processing pipeline
# ---------------------------------------------------------------------------
def process_case(
    manifest: CaseManifest,
    output_dir: Path,
    notice_template: Optional[Path],
    report_template: Optional[Path],
) -> Dict[str, Any]:
    """
    Run the full investigation pipeline on a single :class:`CaseManifest`.

    Args:
        manifest: Case manifest with file paths.
        output_dir: Base directory for case outputs.
        notice_template: Path to notice DOCX template (or None).
        report_template: Path to report DOCX template (or None).

    Returns a summary dict with paths to all generated outputs.
    """
    # Step 1: extract docs and build canonical case
    extracted_docs = extract_case_documents(manifest)
    canonical_case = build_canonical_case(manifest, extracted_docs)

    # Step 2: dynamic output folder
    output_folder_name = build_output_folder_name(manifest, canonical_case)
    case_output_dir = ensure_dir(output_dir / output_folder_name)

    # Step 3: validate, reconcile
    validation = validate_tax_case(canonical_case)
    discrepancies = reconcile_case(canonical_case)
    logger.info("Starting LLM review analysis for case: %s", canonical_case.case_id)
    llm_review = run_vllm_review(canonical_case, discrepancies, validation, extracted_docs)
    
    if llm_review.get("_fallback_reason_detail") == "LLM connection failed":
        logger.info("LLM review using deterministic fallback (LLM unavailable)")
    else:
        logger.info("LLM review completed via API call")
        
    decision = compose_decision(discrepancies, llm_review)

    generated_files: Dict[str, str] = {}
    context = default_notice_context(canonical_case, discrepancies, decision)

    # ----- Report generation -----
    report_docx = case_output_dir / "Tax_Investigation_Report.docx"

    if report_template and Path(report_template).exists():
        try:
            render_docx_template(
                Path(report_template),
                report_docx,
                {
                    **context,
                    "llm_review": llm_review,
                    "report_title": "Tax Investigation Report",
                },
            )
            logger.info("docx good data comes - Report template rendered successfully")

            if report_docx.exists():
                generated_files["report_docx"] = str(report_docx)
                try:
                    generated_files["report_pdf"] = str(
                        convert_docx_to_pdf(report_docx, case_output_dir)
                    )
                except Exception as e:
                    generated_files["report_pdf_error"] = str(e)
                    logger.warning("pdf data not coming - PDF conversion failed: %s", e)
            else:
                report_json_fallback = report_docx.with_suffix(".json")
                generated_files["report_json_fallback"] = str(report_json_fallback)

        except Exception as e:
            fallback_path = case_output_dir / "Tax_Investigation_Report_Fallback.json"
            write_json(
                fallback_path,
                {
                    "context": context,
                    "llm_review": llm_review,
                    "error": str(e),
                },
            )
            generated_files["report_fallback_json"] = str(fallback_path)
            logger.error("docx generation failed - Fallback JSON created: %s", e)
    else:
        fallback_path = case_output_dir / "Tax_Investigation_Report_Fallback.json"
        write_json(
            fallback_path,
            {
                "context": context,
                "llm_review": llm_review,
                "note": "No report template found",
            },
        )
        generated_files["report_fallback_json"] = str(fallback_path)

    # ----- Notice generation -----
    if decision.is_notice_required:
        if not notice_template or not Path(notice_template).exists():
            notice_fallback = case_output_dir / "Notice_Fallback.json"
            write_json(
                notice_fallback,
                {
                    "context": context,
                    "note": "Notice template not found",
                },
            )
            generated_files["notice_fallback_json"] = str(notice_fallback)
        else:
            notice_docx = case_output_dir / "Notice.docx"
            try:
                render_docx_template(
                    Path(notice_template),
                    notice_docx,
                    {
                        **context,
                        "notice_title": "Notice under Section 133(6)",
                    },
                )
                logger.info("docx good data comes - Notice template rendered successfully")

                if notice_docx.exists():
                    generated_files["notice_docx"] = str(notice_docx)
                    try:
                        generated_files["notice_pdf"] = str(
                            convert_docx_to_pdf(notice_docx, case_output_dir)
                        )
                    except Exception as e:
                        generated_files["notice_pdf_error"] = str(e)
                        logger.warning("pdf data not coming - Notice PDF conversion failed: %s", e)
                else:
                    notice_json_fallback = notice_docx.with_suffix(".json")
                    generated_files["notice_json_fallback"] = str(notice_json_fallback)

            except Exception as e:
                notice_fallback = case_output_dir / "Notice_Fallback.json"
                write_json(
                    notice_fallback,
                    {
                        "context": context,
                        "error": str(e),
                    },
                )
                generated_files["notice_fallback_json"] = str(notice_fallback)
                logger.error("notice generation failed - Fallback JSON created: %s", e)

    # ----- Package outputs -----
    package_case_outputs(
        case_dir=case_output_dir,
        manifest=manifest,
        canonical_case=canonical_case,
        validation=validation,
        discrepancies=discrepancies,
        llm_review=llm_review,
        decision=decision,
        generated_files=generated_files,
        extracted_docs=extracted_docs,
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Case:        {canonical_case.case_id}")
    print(f"Decision:    {decision.decision_type}")
    print(f"Notice:      {'YES' if decision.is_notice_required else 'NO'}")
    
    # Show LLM review method
    if llm_review.get("_fallback_reason_detail") == "LLM connection failed":
        print(f"LLM Review:  FALLBACK (LLM unavailable - deterministic analysis used)")
    else:
        print(f"LLM Review:  API (LLM forensic analysis completed)")
    
    print(f"Output:      {case_output_dir}")
    print(f"{'=' * 60}\n")

    return {
        "case_id": canonical_case.case_id,
        "decision_type": decision.decision_type,
        "is_notice_required": decision.is_notice_required,
        "output_dir": str(case_output_dir),
        "generated_files": generated_files,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Tax Investigation System — LLM-powered compliance analysis",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Process a single case by ID (e.g. CASE_001)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List discovered cases without processing",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Override input directory",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # Bootstrap config FIRST — this sets module-level globals
    init_config()

    # Now import the config values AFTER init_config() has set them
    from src.config import INPUT_DIR, NOTICE_TEMPLATE_PATH, REPORT_TEMPLATE_PATH, OUTPUT_DIR

    # Override input directory if provided
    input_dir = Path(args.input) if args.input else INPUT_DIR

    print(f"[DISCOVER] Discovering cases in: {input_dir}")
    manifests = discover_cases(input_dir, NOTICE_TEMPLATE_PATH)
    print(f"   Found {len(manifests)} case(s)\n")

    if args.dry_run:
        for m in manifests:
            print(f"  • {m.case_id:12s} | {m.case_name:30s} | {m.input_mode}")
        return 0

    # Filter by case ID if requested
    if args.case:
        manifests = [m for m in manifests if m.case_id == args.case]
        if not manifests:
            print(f"[ERROR] Case '{args.case}' not found.")
            return 1

    results = []
    for manifest in manifests:
        try:
            result = process_case(
                manifest,
                output_dir=OUTPUT_DIR,
                notice_template=NOTICE_TEMPLATE_PATH,
                report_template=REPORT_TEMPLATE_PATH,
            )
            results.append(result)
        except Exception as e:
            print(f"[ERROR] Error processing {manifest.case_id}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n[DONE] Processed {len(results)} / {len(manifests)} case(s) successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
