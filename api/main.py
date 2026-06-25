import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.models import (
    SessionInitResponse, FileUploadResponse, SessionStatus,
    ProcessStartResponse, ReportData, CaseSummaryCard,
    NoticeData, NoticeDecisionRequest, NoticeDecisionResponse,
)
from api.services.case_processor import (
    create_session, check_uploaded_files, check_templates,
    run_pipeline, get_session_input_dir, get_session_output_dir,
    detect_template_paths, CAPTURED_LOGS, _write_progress,
)
from src.config import init_config
from src.paths import LOG_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

LOG_DIR.mkdir(exist_ok=True)
log_filename = LOG_DIR / f"api_log_{datetime.now().strftime('%Y-%m-%d_%H')}.log"
_file_handler = logging.FileHandler(str(log_filename), encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
logging.getLogger().addHandler(_file_handler)
logger.info("File logging initialized: %s", log_filename)

init_config()

app = FastAPI(title="Tax Investigation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".docx", ".doc"}
FILETYPE_KEYWORDS = {
    "form16": ["form16", "form_16", "form 16"],
    "ais": ["ais"],
    "itr": ["itr_extract", "itr extract", "itr"],
}


def _detect_file_type(filename: str) -> Optional[str]:
    name = Path(filename).stem.lower().replace("-", " ").replace("_", " ").replace(".", " ")
    for ftype, keywords in FILETYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return ftype
    return None


@app.on_event("startup")
async def startup():
    from src.paths import API_INPUT_BASE, API_OUTPUT_BASE
    API_INPUT_BASE.mkdir(parents=True, exist_ok=True)
    API_OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    logger.info("API directories initialized")

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/session/init", response_model=SessionInitResponse)
async def init_session():
    session_id = create_session()
    report_found, notice_found = check_templates()
    return SessionInitResponse(
        session_id=session_id,
        report_template_found=report_found,
        notice_template_found=notice_found,
    )


@app.post("/api/session/{session_id}/upload")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    session_dir = get_session_input_dir(session_id)
    if not session_dir.exists():
        raise HTTPException(404, "Session not found")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: xlsx, xls, docx, doc")

    ftype = _detect_file_type(file.filename)
    if not ftype:
        raise HTTPException(400, f"Cannot detect file type from filename: {file.filename}. Name should contain Form16, AIS, or ITR.")

    dest = session_dir / f"{ftype}{ext}"
    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded %s as %s (%d bytes)", file.filename, dest.name, len(content))

    uploaded = check_uploaded_files(session_id)
    return FileUploadResponse(
        session_id=session_id,
        uploaded_files=uploaded,
        all_uploaded=len(uploaded) >= 3,
        message=f"{file.filename} uploaded as {ftype}",
    )


@app.post("/api/session/{session_id}/upload-template")
async def upload_template(session_id: str, template_type: str = Form(...), file: UploadFile = File(...)):
    session_dir = get_session_input_dir(session_id)
    if not session_dir.exists():
        raise HTTPException(404, "Session not found")
    if template_type not in ("report", "notice"):
        raise HTTPException(400, "template_type must be 'report' or 'notice'")

    tpl_dir = session_dir / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    dest = tpl_dir / f"{template_type}_template.docx"
    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded %s template: %s", template_type, file.filename)

    return {"session_id": session_id, f"{template_type}_template_uploaded": True}


@app.get("/api/session/{session_id}/status", response_model=SessionStatus)
async def get_session_status(session_id: str):
    session_dir = get_session_input_dir(session_id)
    if not session_dir.exists():
        raise HTTPException(404, "Session not found")

    uploaded = check_uploaded_files(session_id)
    report_found, notice_found = check_templates()

    tpl_dir = session_dir / "templates"
    report_uploaded = (tpl_dir / "report_template.docx").exists()
    notice_uploaded = (tpl_dir / "notice_template.docx").exists()

    templates_ready = (report_found or report_uploaded) and (notice_found or notice_uploaded)

    step = "upload"
    status_file = session_dir / "_step.txt"
    if status_file.exists():
        step = status_file.read_text().strip()

    return SessionStatus(
        session_id=session_id,
        step=step,
        uploaded_files=uploaded,
        all_uploaded=len(uploaded) >= 3,
        report_template_found=report_found,
        notice_template_found=notice_found,
        report_template_uploaded=report_uploaded,
        notice_template_uploaded=notice_uploaded,
        all_templates_ready=templates_ready,
    )


@app.get("/api/session/{session_id}/progress")
async def get_progress(session_id: str):
    session_dir = get_session_input_dir(session_id)

    step_file = session_dir / "_step.txt"
    step = "upload"
    if step_file.exists():
        step = step_file.read_text().strip()

    error_file = session_dir / "_error.txt"
    error_msg = None
    if error_file.exists():
        error_msg = error_file.read_text().strip()

    result_ready = False
    result_file = session_dir / "_result.json"
    if result_file.exists():
        result_ready = True

    progress_file = session_dir / "_progress.json"
    if progress_file.exists():
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)
        data["step"] = step
        data["error"] = error_msg
        data["result_ready"] = result_ready

        log_offset_file = session_dir / "_log_offset.txt"
        offset = 0
        if log_offset_file.exists():
            try:
                offset = int(log_offset_file.read_text().strip())
            except ValueError:
                offset = 0
        data["logs"] = CAPTURED_LOGS[offset:]
        data["log_offset"] = len(CAPTURED_LOGS)
        return data

    return {
        "step": step,
        "progress": 0 if step == "processing" else 100 if step in ("report", "error") else 0,
        "message": "Waiting..." if step == "processing" else step,
        "error": error_msg,
        "result_ready": result_ready,
        "logs": [],
        "log_offset": 0,
    }


def _run_pipeline_in_thread(session_id: str):
    """Run the full pipeline in a background thread so /progress can be polled."""
    try:
        result = run_pipeline(session_id)
        result_file = get_session_input_dir(session_id) / "_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        (get_session_input_dir(session_id) / "_step.txt").write_text("report")
        logger.info("Pipeline completed for session %s", session_id)
    except Exception as e:
        logger.exception("Pipeline failed for session %s", session_id)
        (get_session_input_dir(session_id) / "_step.txt").write_text("error")
        _write_progress(session_id, "error", 0, f"Pipeline failed: {e}")
        with open(get_session_input_dir(session_id) / "_error.txt", "w", encoding="utf-8") as f:
            f.write(str(e))


@app.post("/api/session/{session_id}/process")
def start_processing(session_id: str):
    session_dir = get_session_input_dir(session_id)
    if not session_dir.exists():
        raise HTTPException(404, "Session not found")

    uploaded = check_uploaded_files(session_id)
    if len(uploaded) < 3:
        raise HTTPException(400, f"Not all files uploaded. Missing: {[k for k in ('form16','ais','itr') if k not in uploaded]}")

    (session_dir / "_step.txt").write_text("processing")
    _write_progress(session_id, "queued", 2, "Pipeline queued, starting...")

    thread = threading.Thread(target=_run_pipeline_in_thread, args=(session_id,), daemon=True)
    thread.start()

    return {"status": "started", "session_id": session_id, "message": "Pipeline started in background"}


@app.get("/api/session/{session_id}/report", response_model=ReportData)
async def get_report(session_id: str):
    output_dir = get_session_output_dir(session_id)
    if not output_dir.exists():
        raise HTTPException(404, "Output not found")

    case_summary_path = output_dir / "Case_Summary.json"
    canonical_path = output_dir / "Canonical_Tax_Case.json"
    disc_path = output_dir / "Discrepancy_Register.json"
    llm_path = output_dir / "LLM_Review.json"

    case_summary = _read_json(case_summary_path)
    canonical = _read_json(canonical_path)
    discrepancies = _read_json(disc_path) or []
    llm_review = _read_json(llm_path) or {}

    llm_cs = llm_review.get("case_summary", {})
    cards = CaseSummaryCard(
        risk_level=llm_cs.get("overall_risk", "unknown"),
        findings_count=len(llm_review.get("findings", [])),
        notice_candidate=llm_cs.get("notice_candidate", False),
        material_discrepancy_count=llm_cs.get("material_discrepancy_count", 0),
    )

    files = {}
    for f in output_dir.iterdir():
        if f.is_file():
            files[f.name] = str(f)

    return ReportData(
        case_summary=case_summary or {},
        canonical_case=canonical or {},
        discrepancies=discrepancies,
        llm_review=llm_review,
        decision_type=case_summary.get("decision_type", "UNKNOWN") if case_summary else "UNKNOWN",
        is_notice_required=case_summary.get("is_notice_required", False) if case_summary else False,
        summary_cards=cards,
        generated_files=files,
    )


@app.get("/api/session/{session_id}/notice", response_model=NoticeData)
async def get_notice(session_id: str):
    output_dir = get_session_output_dir(session_id)
    if not output_dir.exists():
        raise HTTPException(404, "Output not found")

    case_summary = _read_json(output_dir / "Case_Summary.json") or {}
    canonical = _read_json(output_dir / "Canonical_Tax_Case.json") or {}
    discrepancies = _read_json(output_dir / "Discrepancy_Register.json") or []
    llm_review = _read_json(output_dir / "LLM_Review.json") or {}

    identity = canonical.get("identity", {})

    notice_files = {}
    for fname in ["Notice.docx", "Notice.pdf", "Notice_Fallback.json"]:
        fp = output_dir / fname
        if fp.exists():
            notice_files[fname] = str(fp)

    return NoticeData(
        case_id=case_summary.get("case_id", "N/A"),
        assessee_name=identity.get("name"),
        pan=identity.get("pan"),
        assessment_year=identity.get("assessment_year"),
        discrepancies=discrepancies,
        llm_review=llm_review,
        decision=case_summary,
        notice_files=notice_files,
        preview_available="Notice.pdf" in notice_files,
    )


@app.post("/api/session/{session_id}/notice-decision", response_model=NoticeDecisionResponse)
async def notice_decision(session_id: str, req: NoticeDecisionRequest):
    session_dir = get_session_input_dir(session_id)
    if not session_dir.exists():
        raise HTTPException(404, "Session not found")

    if req.generate_notice:
        output_dir = get_session_output_dir(session_id)
        (session_dir / "_step.txt").write_text("notice_generated")

        notice_files = {}
        if output_dir.exists():
            for fname in ["Notice.docx", "Notice.pdf"]:
                fp = output_dir / fname
                if fp.exists():
                    notice_files[fname] = str(fp)

        return NoticeDecisionResponse(
            session_id=session_id,
            notice_generated=True,
            notice_files=notice_files,
            message="Notice generation confirmed",
        )
    else:
        (session_dir / "_step.txt").write_text("complete")
        return NoticeDecisionResponse(
            session_id=session_id,
            notice_generated=False,
            message="Notice skipped. Case closed.",
        )


@app.get("/api/files/{session_id}/{filename}")
async def serve_file(session_id: str, filename: str):
    for base in [get_session_output_dir(session_id), get_session_input_dir(session_id)]:
        fp = base / filename
        if fp.exists():
            media_type = "application/pdf" if filename.endswith(".pdf") else None
            disp = "inline" if filename.endswith(".pdf") else "attachment"
            return FileResponse(str(fp), media_type=media_type, filename=filename, content_disposition_type=disp)
    raise HTTPException(404, "File not found")


@app.get("/api/session/{session_id}/logs")
async def get_logs(session_id: str, offset: int = Query(0, ge=0)):
    logs = CAPTURED_LOGS[offset:]
    return JSONResponse(content={"logs": logs, "total": len(CAPTURED_LOGS)})


def _read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
