from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class SessionInitResponse(BaseModel):
    session_id: str
    required_files: List[str] = ["form16", "ais", "itr"]
    report_template_found: bool = False
    notice_template_found: bool = False
    message: str = "Session created"


class FileUploadResponse(BaseModel):
    session_id: str
    uploaded_files: List[str]
    all_uploaded: bool
    message: str


class TemplateUploadResponse(BaseModel):
    session_id: str
    report_template_uploaded: bool = False
    notice_template_uploaded: bool = False
    all_templates_ready: bool = False
    message: str


class SessionStatus(BaseModel):
    session_id: str
    step: str = "upload"
    uploaded_files: List[str] = Field(default_factory=list)
    all_uploaded: bool = False
    report_template_found: bool = False
    notice_template_found: bool = False
    report_template_uploaded: bool = False
    notice_template_uploaded: bool = False
    all_templates_ready: bool = True
    error: Optional[str] = None


class ProcessStartResponse(BaseModel):
    session_id: str
    status: str = "processing"
    message: str = "Processing started"


class ProcessStatus(BaseModel):
    session_id: str
    status: str = "processing"
    messages: List[str] = Field(default_factory=list)
    progress: int = 0
    error: Optional[str] = None


class CaseSummaryCard(BaseModel):
    risk_level: str
    findings_count: int
    notice_candidate: bool
    material_discrepancy_count: int


class ReportData(BaseModel):
    case_summary: Dict[str, Any]
    canonical_case: Dict[str, Any]
    discrepancies: List[Dict[str, Any]]
    llm_review: Dict[str, Any]
    decision_type: str
    is_notice_required: bool
    summary_cards: CaseSummaryCard
    generated_files: Dict[str, str]


class NoticeData(BaseModel):
    case_id: str
    assessee_name: Optional[str]
    pan: Optional[str]
    assessment_year: Optional[str]
    discrepancies: List[Dict[str, Any]]
    llm_review: Dict[str, Any]
    decision: Dict[str, Any]
    notice_files: Dict[str, str]
    preview_available: bool


class NoticeDecisionRequest(BaseModel):
    session_id: str
    generate_notice: bool


class NoticeDecisionResponse(BaseModel):
    session_id: str
    notice_generated: bool
    notice_files: Dict[str, str] = Field(default_factory=dict)
    message: str
