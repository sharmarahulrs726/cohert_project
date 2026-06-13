"""
vLLM analytical reviewer — uses an LLM to generate a discrepancy analysis report.

If the LLM call fails, a deterministic fallback produces the review based
solely on rule-based discrepancy data.
"""

import json
import logging
from typing import Any, Dict, List

from openai import OpenAI

from src.config import VLLM_BASE_URL, VLLM_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)
from src.models import CanonicalTaxCase
from src.discrepancies import Discrepancy, asdict


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------
client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)


# ---------------------------------------------------------------------------
# JSON schema for structured LLM output
# ---------------------------------------------------------------------------
LLM_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "case_summary": {
            "type": "object",
            "properties": {
                "overall_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                "material_discrepancy_count": {"type": "integer"},
                "manual_review_required": {"type": "boolean"},
                "notice_candidate": {"type": "boolean"},
                "summary_text": {"type": "string"},
            },
            "required": [
                "overall_risk",
                "material_discrepancy_count",
                "manual_review_required",
                "notice_candidate",
                "summary_text",
            ],
            "additionalProperties": False,
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_id": {"type": "string"},
                    "category": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["confirmed", "probable", "uncertain"],
                    },
                    "materiality": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "difference_summary": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "source_support": {"type": "array", "items": {"type": "string"}},
                    "sheet_references": {"type": "array", "items": {"type": "string"}},
                    "manual_review_required": {"type": "boolean"},
                },
                "required": [
                    "finding_id",
                    "category",
                    "status",
                    "materiality",
                    "difference_summary",
                    "reasoning",
                    "source_support",
                    "sheet_references",
                    "manual_review_required",
                ],
                "additionalProperties": False,
            },
        },
        "investigation_narrative": {
            "type": "object",
            "properties": {
                "facts_established": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "issues_observed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "uncertainties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "recommended_next_step": {
                    "type": "string",
                    "enum": ["no_action", "manual_review", "issue_notice"],
                },
            },
            "required": [
                "facts_established",
                "issues_observed",
                "uncertainties",
                "recommended_next_step",
            ],
            "additionalProperties": False,
        },
        "validation_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "responsible_party": {"type": "string", "enum": ["assessee", "deductor", "bank", "registry", "third_party"]},
                    "document_requested": {"type": "string"},
                    "legal_basis": {"type": "string"},
                },
                "required": ["step_id", "description", "priority", "responsible_party", "document_requested", "legal_basis"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["case_summary", "findings", "investigation_narrative", "validation_steps"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# LLM message builder
# ---------------------------------------------------------------------------
def build_llm_messages(
    canonical_case: CanonicalTaxCase,
    discrepancies: List[Discrepancy],
    validation: Dict[str, Any],
    extracted_docs: Dict[str, Dict[str, Any]] | None = None,
) -> List[Dict[str, str]]:
    """Build the system + user messages for the LLM review call."""
    discrepancy_list = [asdict(d) for d in discrepancies]

    # Include raw extracted document data (all sheets from XLSX, full text from DOCX)
    raw_docs = {}
    if extracted_docs:
        for role, doc in extracted_docs.items():
            raw_docs[role] = {
                "file_name": doc.get("file_name"),
                "extraction_method": doc.get("extraction_method"),
                "markdown": doc.get("markdown", "")[:15000],  # cap length for token limits
                "docling_json": doc.get("docling_json", {}),
            }

    system_prompt = (
        "You are a senior Indian Income Tax Officer with deep expertise in ITR "
        "verification, TDS reconciliation, and tax compliance analysis. Your task is "
        "to forensically analyse the tax documents provided below and identify critical "
        "discrepancies, mismatch, or compliance issue that may warrant a scrutiny "
        "notice under the Income Tax Act, 1961.\n\n"
        "You have access to TWO sources of evidence:\n"
        "1. PRE-COMPUTED DISCREPANCIES (Discrepancy_Register.json) — rule-based "
        "comparisons between Form 16, AIS, and ITR fields (salary, TDS, interest, "
        "dividend, securities, bank deposits vs total income). These are your primary "
        "source of truth but may miss context.\n"
        "2. RAW EXTRACTED DOCUMENTS (data_extraction.json) — complete sheet-by-sheet "
        "data from every XLSX/DOCX (AIS: Summary, Part A-TDS, Part A2 Property, "
        "Part C Tax Paid, Part E SFT; Form 16; ITR: all schedules). Use these for "
        "independent forensic verification.\n\n"
        "YOUR ANALYSIS MUST:\n"
        "- Cross-reference EACH pre-computed discrepancy against the raw sheets to "
        "confirm, refine, or reject it with specific cell/sheet references\n"
        "- Identify ADDITIONAL discrepancies NOT caught by rules (e.g., property "
        "income mismatch, TDS credit mismatch across quarters, SFT transaction "
        "inconsistencies, deduction claim anomalies)\n"
        "- Assess materiality per IT Act thresholds (₹50k general, ₹1L bank deposits)\n"
        "- Recommend specific validation steps: document requests, third-party "
        "verification, assessee questioning\n"
        "- Output ONLY valid JSON matching the required schema"
    )

    user_prompt = (
        "Forensically analyse this tax case. Cross-reference pre-computed discrepancies "
        "with raw extracted sheets. Identify all mismatches, compliance issues, and "
        "recommend validation steps for scrutiny notice under Section 133(6).\n\n"
        "DATA:\n"
        + json.dumps({
            "canonical_case": json.loads(canonical_case.model_dump_json()),
            "validation": validation,
            "precomputed_discrepancies": discrepancy_list,
            "raw_extracted_documents": raw_docs,
        }, ensure_ascii=False, indent=2, default=str)
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------------
# Deterministic fallback review
# ---------------------------------------------------------------------------
def fallback_llm_review(
    canonical_case: CanonicalTaxCase,
    discrepancies: List[Discrepancy],
    validation: Dict[str, Any],
) -> Dict[str, Any]:
    """Produce a review dict using rule-based logic when the LLM is unavailable."""
    material_count = len(
        [d for d in discrepancies if d.materiality in ("medium", "high")]
    )
    high_count = len([d for d in discrepancies if d.materiality == "high"])
    notice_candidate = any(d.notice_candidate for d in discrepancies)
    manual_review_required = high_count > 0 or not validation.get("is_valid", True)
    
    logger.info(
        "Deterministic fallback active - LLM unavailable. "
        "Material count: %d, High severity: %d, Notice candidate: %s, Manual review required: %s",
        material_count, high_count, notice_candidate, manual_review_required
    )

    if high_count > 0 or notice_candidate:
        overall_risk = "high"
    elif material_count > 0:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    findings = []
    for d in discrepancies:
        findings.append({
            "finding_id": d.discrepancy_id,
            "category": d.category,
            "status": "confirmed",
            "materiality": (
                d.materiality if d.materiality in ("low", "medium", "high") else "low"
            ),
            "difference_summary": (
                f"Source={d.source_reported_value}, Declared={d.declared_value}, "
                f"Delta={d.delta}"
            ),
            "reasoning": d.reason,
            "source_support": [d.category],
            "sheet_references": [d.category],
            "manual_review_required": d.manual_review_required,
        })

    validation_steps = []
    if notice_candidate:
        validation_steps.append({
            "step_id": "VS-001",
            "description": "Issue notice under Section 133(6) calling for books of accounts and supporting documents for discrepancies identified",
            "priority": "high",
            "responsible_party": "assessee",
            "document_requested": "Books of accounts, bank statements, property documents, TDS certificates",
            "legal_basis": "Section 133(6) of Income Tax Act, 1961"
        })
    if high_count > 0:
        validation_steps.append({
            "step_id": "VS-002",
            "description": "Verify TDS credits with deductors (Form 16/16A) and cross-check with TRACES",
            "priority": "high",
            "responsible_party": "deductor",
            "document_requested": "TDS certificates, Form 26AS/TRACES statement",
            "legal_basis": "Section 203AA read with Rule 31AB"
        })

    return {
        "case_summary": {
            "overall_risk": overall_risk,
            "material_discrepancy_count": material_count,
            "manual_review_required": manual_review_required,
            "notice_candidate": notice_candidate,
            "summary_text": (
                f"{len(discrepancies)} discrepancy(s) detected; "
                f"{material_count} material discrepancy(s)."
            ),
        },
        "findings": findings,
        "investigation_narrative": {
            "facts_established": [
                f"Case ID: {canonical_case.case_id}",
                f"PAN: {canonical_case.identity.pan or 'NA'}",
                f"Assessment Year: {canonical_case.identity.assessment_year or 'NA'}",
            ],
            "issues_observed": (
                [d.reason for d in discrepancies] if discrepancies
                else ["No discrepancies observed"]
            ),
            "uncertainties": validation.get("issues", []),
            "recommended_next_step": (
                "issue_notice"
                if notice_candidate
                else ("manual_review" if manual_review_required else "no_action")
            ),
        },
        "validation_steps": validation_steps,
    }


# ---------------------------------------------------------------------------
# Main review entry point
# ---------------------------------------------------------------------------
def run_vllm_review(
    canonical_case: CanonicalTaxCase,
    discrepancies: List[Discrepancy],
    validation: Dict[str, Any],
    extracted_docs: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    Execute the LLM-based review with a deterministic fallback.

    Returns a dict conforming to :data:`LLM_OUTPUT_SCHEMA`.
    """
    try:
        messages = build_llm_messages(canonical_case, discrepancies, validation, extracted_docs)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
            extra_body={"structured_outputs": {"json": LLM_OUTPUT_SCHEMA}},
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
            )
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM not connected: %s — using deterministic fallback", e)
        logger.info("PDF data not coming - LLM unavailable for forensic analysis")
        review = fallback_llm_review(canonical_case, discrepancies, validation)
        review["_fallback_reason"] = str(e)
        review["_fallback_reason_detail"] = "LLM connection failed"
        return review
