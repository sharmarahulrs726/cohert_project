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
    """
    notice_required = any(d.notice_candidate for d in discrepancies)

    if not discrepancies:
        decision_type = "NO_DISCREPANCY"
        reason_codes = ["NO_MATERIAL_DISCREPANCY"]
    elif notice_required:
        decision_type = "NOTICE_AND_REPORT"
        reason_codes = ["RULE_TRIGGERED_NOTICE"]
    else:
        decision_type = "REPORT_ONLY"
        reason_codes = ["DISCREPANCY_REVIEW_ONLY"]

    return DecisionResult(
        is_notice_required=notice_required,
        decision_type=decision_type,
        reason_codes=reason_codes,
        llm_summary=llm_summary,
    )
