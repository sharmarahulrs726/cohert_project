"""
Canonical data models for the Tax Investigation System.

Defines the structured representation of taxpayer identity and all
financial documents (Form 16, AIS, ITR) extracted from source files.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaxpayerIdentity(BaseModel):
    """Identity information of a taxpayer extracted from documents."""

    name: Optional[str] = None
    pan: Optional[str] = None
    assessment_year: Optional[str] = None


class Form16Data(BaseModel):
    """Data extracted from Form 16 (salary/TDS certificate from employer)."""

    employer_name: Optional[str] = None
    tan: Optional[str] = None
    gross_salary: Decimal = Decimal("0")
    tds_deducted: Decimal = Decimal("0")
    chapter_via_deductions: Decimal = Decimal("0")


class AISData(BaseModel):
    """Data extracted from Annual Information Statement (AIS)."""

    salary: Decimal = Decimal("0")
    interest: Decimal = Decimal("0")
    dividend: Decimal = Decimal("0")
    securities: Decimal = Decimal("0")
    tds: Decimal = Decimal("0")
    bank_deposits: Decimal = Decimal("0")


class ITRData(BaseModel):
    """Data extracted from Income Tax Return (ITR) extract."""

    salary: Decimal = Decimal("0")
    other_sources: Decimal = Decimal("0")
    interest: Decimal = Decimal("0")
    dividend: Decimal = Decimal("0")
    securities: Decimal = Decimal("0")
    tds: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")
    total_income: Decimal = Decimal("0")


class CanonicalTaxCase(BaseModel):
    """
    Canonical representation of a complete tax case.

    Aggregates identity information along with structured data from
    Form 16, AIS, and ITR extracts, plus provenance metadata.
    """

    case_id: str
    identity: TaxpayerIdentity
    form16: Form16Data
    ais: AISData
    itr: ITRData
    provenance: Dict[str, Any] = Field(default_factory=dict)
