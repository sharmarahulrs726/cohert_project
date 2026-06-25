import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.case_discovery import CaseManifest, asdict
from src.config import init_config
from src.paths import SAMPLE_DIR, API_INPUT_BASE, API_OUTPUT_BASE, LOG_DIR
from src.discrepancies import Discrepancy
from src.extraction import extract_with_docling
from src.mapping import build_canonical_case
from src.validation import validate_tax_case
from src.discrepancies import reconcile_case
from src.llm_reviewer import run_vllm_review
from src.decision import compose_decision, DecisionResult
from src.document_gen import (
    default_notice_context,
    render_docx_template,
    convert_docx_to_pdf,
)
from src.output import write_json, package_case_outputs

logger = logging.getLogger(__name__)

CAPTURED_LOGS: List[str] = []


class LogCaptureHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        CAPTURED_LOGS.append(self.format(record))


_capture_handler = LogCaptureHandler()
_capture_handler.setLevel(logging.INFO)
_capture_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logging.getLogger().addHandler(_capture_handler)


def _reset_logs():
    CAPTURED_LOGS.clear()


def _get_logs() -> List[str]:
    return list(CAPTURED_LOGS)


def _write_progress(session_id: str, step: str, progress: int, message: str):
    progress_file = get_session_input_dir(session_id) / "_progress.json"
    progress_file.write_text(json.dumps({
        "step": step,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False), encoding="utf-8")


def create_session() -> str:
    session_id = uuid.uuid4().hex[:12]
    (API_INPUT_BASE / session_id).mkdir(parents=True, exist_ok=True)
    (API_OUTPUT_BASE / session_id).mkdir(parents=True, exist_ok=True)
    (API_INPUT_BASE / session_id / "templates").mkdir(parents=True, exist_ok=True)
    return session_id


def get_session_input_dir(session_id: str) -> Path:
    return API_INPUT_BASE / session_id


def get_session_output_dir(session_id: str) -> Path:
    return API_OUTPUT_BASE / session_id


def check_uploaded_files(session_id: str) -> List[str]:
    session_dir = get_session_input_dir(session_id)
    uploaded = []
    for fname in session_dir.iterdir():
        if fname.is_file() and fname.suffix.lower() in (".xlsx", ".xls", ".docx", ".doc"):
            name_lower = fname.stem.lower()
            if "form16" in name_lower or "form_16" in name_lower or "form 16" in name_lower:
                if "form16" not in uploaded:
                    uploaded.append("form16")
            elif fname.stem.lower() == "ais":
                if "ais" not in uploaded:
                    uploaded.append("ais")
            elif "itr" in name_lower:
                if "itr" not in uploaded:
                    uploaded.append("itr")
    return uploaded


def check_templates() -> tuple:
    init_config()
    from src.config import NOTICE_TEMPLATE_PATH, REPORT_TEMPLATE_PATH
    return (
        REPORT_TEMPLATE_PATH is not None and Path(REPORT_TEMPLATE_PATH).exists(),
        NOTICE_TEMPLATE_PATH is not None and Path(NOTICE_TEMPLATE_PATH).exists(),
    )


def detect_template_paths(
    session_id: str,
    user_report_template: Optional[Path] = None,
    user_notice_template: Optional[Path] = None,
):
    from src.config import NOTICE_TEMPLATE_PATH, REPORT_TEMPLATE_PATH

    report_tpl = user_report_template or (Path(REPORT_TEMPLATE_PATH) if REPORT_TEMPLATE_PATH else None)
    notice_tpl = user_notice_template or (Path(NOTICE_TEMPLATE_PATH) if NOTICE_TEMPLATE_PATH else None)

    if report_tpl and report_tpl.exists():
        pass
    else:
        user_report = get_session_input_dir(session_id) / "templates" / "report_template.docx"
        if user_report.exists():
            report_tpl = user_report
        else:
            report_tpl = None

    if notice_tpl and notice_tpl.exists():
        pass
    else:
        user_notice = get_session_input_dir(session_id) / "templates" / "notice_template.docx"
        if user_notice.exists():
            notice_tpl = user_notice
        else:
            notice_tpl = None

    return report_tpl, notice_tpl


def run_pipeline(session_id: str) -> Dict[str, Any]:
    _reset_logs()
    session_input = get_session_input_dir(session_id)
    session_output = get_session_output_dir(session_id)

    _write_progress(session_id, "initializing", 5, "Initializing pipeline...")
    init_config()

    files = {}
    for f in session_input.iterdir():
        if f.is_file() and f.suffix.lower() in (".xlsx", ".xls", ".docx", ".doc"):
            name_lower = f.stem.lower()
            if any(x in name_lower for x in ("form16", "form_16", "form 16")):
                files["form16"] = str(f)
            elif name_lower == "ais":
                files["ais"] = str(f)
            elif "itr" in name_lower:
                files["itr"] = str(f)

    if len(files) < 3:
        missing = [k for k in ("form16", "ais", "itr") if k not in files]
        _write_progress(session_id, "error", 0, f"Missing files: {missing}")
        raise ValueError(f"Missing files: {missing}")

    _write_progress(session_id, "extracting", 10, "Extracting data from uploaded documents...")

    manifest = CaseManifest(
        case_id=f"CASE_{session_id}",
        case_name=f"Session_{session_id}",
        input_mode="session",
        case_path=str(session_input),
        files=files,
        template_path="",
        discovered_at=datetime.now().isoformat(),
        file_hashes={},
    )

    report_tpl, notice_tpl = detect_template_paths(session_id)

    result = process_case_wrapper(session_id, manifest, session_output, notice_tpl, report_tpl)

    log_data = _get_logs()
    result["logs"] = log_data
    return result


def process_case_wrapper(
    session_id: str,
    manifest: CaseManifest,
    output_dir: Path,
    notice_template: Optional[Path],
    report_template: Optional[Path],
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_progress(session_id, "extracting", 15, "Extracting sheets from Form16, AIS, ITR...")
    extracted_docs = {
        role: extract_with_docling(Path(path))
        for role, path in manifest.files.items()
    }
    logger.info("documents extracted for case: %s", manifest.case_id)

    _write_progress(session_id, "mapping", 25, "Building canonical case data...")
    canonical_case = build_canonical_case(manifest, extracted_docs)
    logger.info("canonical case built for: %s", manifest.case_id)

    _write_progress(session_id, "validating", 35, "Validating data quality...")
    validation = validate_tax_case(canonical_case)
    logger.info("validation complete for: %s", manifest.case_id)

    _write_progress(session_id, "discrepancies", 45, "Running rule-based discrepancy analysis...")
    discrepancies = reconcile_case(canonical_case)
    logger.info("discrepancy analysis complete for: %s", manifest.case_id)

    _write_progress(session_id, "llm_review", 55, "Running LLM forensic review...")
    llm_review = run_vllm_review(canonical_case, discrepancies, validation, extracted_docs)

    if llm_review.get("_fallback_reason_detail") == "LLM connection failed":
        logger.info("LLM review used deterministic fallback")
        _write_progress(session_id, "llm_review", 65, "LLM review used deterministic fallback")
    else:
        logger.info("LLM review completed via API call")
        _write_progress(session_id, "llm_review", 65, "LLM review completed via API")

    _write_progress(session_id, "decision", 70, "Composing decision...")
    decision = compose_decision(discrepancies, llm_review)
    logger.info("decision composed: %s", decision.decision_type)

    generated_files: Dict[str, str] = {}
    context = default_notice_context(canonical_case, discrepancies, decision)

    _write_progress(session_id, "report_gen", 75, "Generating report DOCX/PDF...")
    report_docx = output_dir / "Tax_Investigation_Report.docx"
    if report_template and report_template.exists():
        try:
            render_docx_template(
                report_template, report_docx,
                {**context, "llm_review": llm_review, "report_title": "Tax Investigation Report"},
            )
            logger.info("report template rendered successfully")
            if report_docx.exists():
                generated_files["report_docx"] = str(report_docx)
                try:
                    pdf_path = convert_docx_to_pdf(report_docx, output_dir)
                    generated_files["report_pdf"] = str(pdf_path)
                    logger.info("report PDF generated")
                except Exception as e:
                    generated_files["report_pdf_error"] = str(e)
                    logger.warning("report PDF conversion failed: %s", e)
        except Exception as e:
            logger.error("report docx generation failed: %s", e)
            fallback = output_dir / "Tax_Investigation_Report_Fallback.json"
            write_json(fallback, {"context": context, "error": str(e)})
            generated_files["report_fallback_json"] = str(fallback)

    if decision.is_notice_required:
        _write_progress(session_id, "notice_gen", 80, "Generating notice DOCX/PDF...")
        if not notice_template or not notice_template.exists():
            logger.warning("Notice required but no template found")
            notice_fallback = output_dir / "Notice_Fallback.json"
            write_json(notice_fallback, {"context": context, "note": "No notice template"})
            generated_files["notice_fallback_json"] = str(notice_fallback)
        else:
            notice_docx = output_dir / "Notice.docx"
            try:
                render_docx_template(
                    notice_template, notice_docx,
                    {**context, "notice_title": "Notice under Section 133(6)"},
                )
                logger.info("notice template rendered successfully")
                if notice_docx.exists():
                    generated_files["notice_docx"] = str(notice_docx)
                    try:
                        pdf_path = convert_docx_to_pdf(notice_docx, output_dir)
                        generated_files["notice_pdf"] = str(pdf_path)
                        logger.info("notice PDF generated")
                    except Exception as e:
                        generated_files["notice_pdf_error"] = str(e)
                        logger.warning("notice PDF conversion failed: %s", e)
            except Exception as e:
                logger.error("notice docx generation failed: %s", e)
                fallback_path = output_dir / "Notice_Fallback.json"
                write_json(fallback_path, {"context": context, "error": str(e)})
                generated_files["notice_fallback_json"] = str(fallback_path)

    _write_progress(session_id, "packaging", 95, "Packaging output files...")
    package_case_outputs(
        case_dir=output_dir,
        manifest=manifest,
        canonical_case=canonical_case,
        validation=validation,
        discrepancies=discrepancies,
        llm_review=llm_review,
        decision=decision,
        generated_files=generated_files,
        extracted_docs=extracted_docs,
    )

    from src.decision import asdict as decision_asdict

    _write_progress(session_id, "complete", 100, "Analysis complete")

    return {
        "case_id": canonical_case.case_id,
        "decision_type": decision.decision_type,
        "is_notice_required": decision.is_notice_required,
        "output_dir": str(output_dir),
        "generated_files": generated_files,
        "canonical_case": json.loads(canonical_case.model_dump_json()),
        "discrepancies": [asdict(d) for d in discrepancies],
        "llm_review": llm_review,
        "validation": validation,
        "decision": decision_asdict(decision),
        "context": context,
    }
