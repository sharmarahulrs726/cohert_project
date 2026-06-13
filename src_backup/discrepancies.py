"""
Deterministic discrepancy engine.

Compares source document values (Form 16 / AIS) against the values declared
in the ITR and flags material differences for further review or notice issuance.
"""

import logging
import uuid
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Dict, List, Optional

from src.models import CanonicalTaxCase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------
@dataclass
class Discrepancy:
    """A single identified discrepancy between source and declared values."""

    discrepancy_id: str
    category: str
    source_reported_value: str
    declared_value: str
    delta: str
    materiality: str
    severity: str
    notice_candidate: bool
    manual_review_required: bool
    reason: str


# ---------------------------------------------------------------------------
# Materiality / severity helpers
# ---------------------------------------------------------------------------
def materiality_band(delta: Decimal) -> str:
    """Classify the magnitude of a discrepancy."""
    d = abs(delta)
    if d == 0:
        return "none"
    if d <= Decimal("1000"):
        return "low"
    if d <= Decimal("50000"):
        return "medium"
    return "high"


def severity_from_band(band: str) -> str:
    """Map materiality band to a severity label."""
    return {
        "none": "none",
        "low": "low",
        "medium": "medium",
        "high": "high",
    }[band]


def notice_trigger(delta: Decimal, category: str) -> bool:
    """Determine whether the discrepancy should trigger a notice."""
    if category == "bank_deposits_vs_total_income" and abs(delta) > Decimal("100000"):
        return True
    if abs(delta) > Decimal("50000"):
        return True
    return False


# ---------------------------------------------------------------------------
# Discrepancy factory
# ---------------------------------------------------------------------------
def make_discrepancy(
    category: str,
    source_value: Decimal,
    declared_value: Decimal,
    reason: str,
) -> Optional[Discrepancy]:
    """Create a :class:`Discrepancy` if the delta is material (> none)."""
    delta = source_value - declared_value
    band = materiality_band(delta)
    if band == "none":
        return None
    return Discrepancy(
        discrepancy_id=str(uuid.uuid4()),
        category=category,
        source_reported_value=str(source_value),
        declared_value=str(declared_value),
        delta=str(delta),
        materiality=band,
        severity=severity_from_band(band),
        notice_candidate=notice_trigger(delta, category),
        manual_review_required=(band == "high"),
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Core reconciliation engine
# ---------------------------------------------------------------------------
def reconcile_case(c: CanonicalTaxCase) -> List[Discrepancy]:
    """
    Compare source-reported amounts (Form 16 / AIS) with ITR-declared amounts.

    Returns a list of material :class:`Discrepancy` objects.
    """
    discrepancies: List[Discrepancy] = []
    rules = [
        (
            "salary",
            c.ais.salary if c.ais.salary > 0 else c.form16.gross_salary,
            c.itr.salary,
            "Salary reported externally is different from the salary declared in ITR.",
        ),
        (
            "tds",
            c.ais.tds if c.ais.tds > 0 else c.form16.tds_deducted,
            c.itr.tds,
            "TDS available in source documents is different from TDS declared in ITR.",
        ),
        (
            "interest",
            c.ais.interest,
            c.itr.interest,
            "Interest income in AIS is different from interest income declared in ITR.",
        ),
        (
            "dividend",
            c.ais.dividend,
            c.itr.dividend,
            "Dividend income in AIS is different from dividend income declared in ITR.",
        ),
        (
            "securities",
            c.ais.securities,
            c.itr.securities,
            "Securities-related values in AIS are different from disclosures in ITR.",
        ),
        (
            "bank_deposits_vs_total_income",
            c.ais.bank_deposits,
            c.itr.total_income,
            "Bank deposits/significant credits appear higher than declared total income "
            "and require investigation.",
        ),
    ]
    for category, source_value, declared_value, reason in rules:
        d = make_discrepancy(category, source_value, declared_value, reason)
        if d:
            discrepancies.append(d)

    return discrepancies
