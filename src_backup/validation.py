"""
Validation module.

Checks a canonical tax case for completeness and data quality issues.
"""

from typing import Any, Dict

from src.models import CanonicalTaxCase


def validate_tax_case(canonical_case: CanonicalTaxCase) -> Dict[str, Any]:
    """
    Validate a canonical tax case and return a summary of issues.

    Checks include:
    - PAN presence
    - Assessment year presence
    - Negative amount detection on key fields
    """
    issues = []
    if canonical_case.identity.pan is None:
        issues.append("PAN not detected")
    if canonical_case.identity.assessment_year is None:
        issues.append("Assessment year not detected")

    for label, value in {
        "form16.gross_salary": canonical_case.form16.gross_salary,
        "form16.tds_deducted": canonical_case.form16.tds_deducted,
        "ais.salary": canonical_case.ais.salary,
        "ais.interest": canonical_case.ais.interest,
        "ais.dividend": canonical_case.ais.dividend,
        "ais.tds": canonical_case.ais.tds,
        "itr.salary": canonical_case.itr.salary,
        "itr.interest": canonical_case.itr.interest,
        "itr.dividend": canonical_case.itr.dividend,
        "itr.tds": canonical_case.itr.tds,
    }.items():
        if value < 0:
            issues.append(f"Negative amount detected at {label}")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
    }
