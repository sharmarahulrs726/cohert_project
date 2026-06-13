"""
Decision composer — determines whether a notice or report should be generated
based on the identified discrepancies and LLM review.
"""

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from src.discrepancies import Discrepancy

logger = logging.getLogger(__name__)


@dataclass
class DecisionResult:
    """Encapsulates the final decision for a tax case."""

    is_notice_required: bool
    decision_type: str
    reason_codes: List[str]
    llm_summary: Dict[str, Any]


def compose_decision(
    discrepancies: List[Discrepancy],
    llm_summary: Dict[str, Any],
) -> DecisionResult:
    """
    Decide whether a notice, report, or neither should be produced.

    Decision types:
    - ``NO_DISCREPANCY``        — no material discrepancies found
    - ``NOTICE_AND_REPORT``     — one or more discrepancies trigger a notice
    - ``REPORT_ONLY``           — discrepancies exist but do not trigger a notice

    Logic:
    1. First check LLM review if available and valid (not fallback)
    2. If LLM says notice needed, honor it
    3. Fallback to rule-based if LLM unavailable or inconclusive
    """
    # Check if LLM review is valid (not fallback)
    llm_valid = (
        llm_summary 
        and not llm_summary.get("_fallback_reason_detail") == "LLM connection failed"
        and llm_summary.get("case_summary", {}).get("notice_candidate") is not None
    )
    
    # Rule-based notice trigger
    rule_notice_required = any(d.notice_candidate for d in discrepancies)
    
    # LLM-based notice decision (if LLM is valid)
    llm_notice_required = False
    if llm_valid:
        llm_notice_required = llm_summary.get("case_summary", {}).get("notice_candidate", False)
        logger.info("LLM review notice_candidate: %s", llm_notice_required)
    
    # Final decision: LLM overrides rules if available and definitive
    if llm_valid:
        notice_required = llm_notice_required
        if llm_notice_required:
            reason_codes = ["LLM_RECOMMENDED_NOTICE"]
        else:
            reason_codes = ["LLM_NO_NOTICE_REQUIRED"]
    else:
        notice_required = rule_notice_required
        if rule_notice_required:
            reason_codes = ["RULE_TRIGGERED_NOTICE"]
        else:
            reason_codes = ["NO_MATERIAL_DISCREPANCY"]
    
    if not discrepancies:
        decision_type = "NO_DISCREPANCY"
        reason_codes = ["NO_MATERIAL_DISCREPANCY"]
        notice_required = False
    elif notice_required:
        decision_type = "NOTICE_AND_REPORT"
    else:
        decision_type = "REPORT_ONLY"

    return DecisionResult(
        is_notice_required=notice_required,
        decision_type=decision_type,
        reason_codes=reason_codes,
        llm_summary=llm_summary,
    )
