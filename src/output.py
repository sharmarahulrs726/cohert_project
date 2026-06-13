"""
Output packaging — writes structured JSON files and audit logs for each case.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from src.utils import ensure_dir, now_iso
from src.models import CanonicalTaxCase
from src.case_discovery import CaseManifest, asdict
from src.discrepancies import Discrepancy
from src.decision import DecisionResult


def write_json(path: Path, data: Any) -> None:
    """Write *data* as pretty-printed JSON to *path*."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def package_case_outputs(
    case_dir: Path,
    manifest: CaseManifest,
    canonical_case: CanonicalTaxCase,
    validation: Dict[str, Any],
    discrepancies: List[Discrepancy],
    llm_review: Dict[str, Any],
    decision: DecisionResult,
    generated_files: Dict[str, str],
    extracted_docs: Dict[str, Dict[str, Any]] | None = None,
) -> None:
    """
    Write all case outputs (summary, discrepancy register, canonical case,
    LLM review, audit log, raw extraction) into *case_dir*.
    """
    ensure_dir(case_dir)

    write_json(
        case_dir / "Case_Summary.json",
        {
            "case_id": canonical_case.case_id,
            "decision_type": decision.decision_type,
            "is_notice_required": decision.is_notice_required,
            "reason_codes": decision.reason_codes,
            "generated_at": now_iso(),
            "generated_files": generated_files,
        },
    )

    write_json(
        case_dir / "Discrepancy_Register.json",
        [asdict(d) for d in discrepancies],
    )

    write_json(
        case_dir / "Canonical_Tax_Case.json",
        json.loads(canonical_case.model_dump_json()),
    )

    logger.info("Saving LLM_Review.json (Review method: %s)", 
                "Deterministic fallback" if llm_review.get("_fallback_reason_detail") == "LLM connection failed" else "LLM API")

    write_json(case_dir / "LLM_Review.json", llm_review)

    write_json(
        case_dir / "Audit_Log.json",
        {
            "manifest": asdict(manifest),
            "validation": validation,
            "decision": asdict(decision),
            "generated_at": now_iso(),
        },
    )

    if extracted_docs:
        extraction_output = {}
        for role, doc in extracted_docs.items():
            extraction_output[role] = {
                "file_name": doc.get("file_name"),
                "source_path": doc.get("source_path"),
                "extracted_at": doc.get("extracted_at"),
                "extraction_method": doc.get("extraction_method"),
                "docling_json": doc.get("docling_json", {}),
                "markdown": doc.get("markdown", ""),
            }
        write_json(case_dir / "data_extraction.json", extraction_output)
