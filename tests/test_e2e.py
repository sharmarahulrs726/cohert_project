"""
End-to-end test for the Tax Investigation System.
Tests each module's core functions and runs the full pipeline.
"""
import sys
import os
import tempfile
from pathlib import Path

# Add project root to path so 'from src.xxx' imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Bootstrap config FIRST so module-level globals are set
import src.config
src.config.init_config()

# Clean up old output from previous runs to avoid stale data confusion
import shutil
if src.config.OUTPUT_DIR.exists():
    for item in src.config.OUTPUT_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)

print("=" * 70)
print("E2E TEST: Tax Investigation System")
print("=" * 70)

errors = []

def check(condition, msg):
    if condition:
        print(f"  [PASS] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        errors.append(msg)

# ===================================================================
# 1. TEST: Utility functions
# ===================================================================
print("\n--- 1. Utility Helpers ---")
from src.utils import sha256_file, now_iso, safe_decimal, ensure_dir
from decimal import Decimal

ts = now_iso()
check("T" in ts and "Z" in ts, f"now_iso() returns valid ISO format: {ts}")

d = safe_decimal("1,23,456")
check(d == Decimal("123456"), f"safe_decimal parses comma-separated: {d}")

d2 = safe_decimal("Rs. 50,000")
check(d2 == Decimal("50000"), f"safe_decimal strips currency: {d2}")

d3 = safe_decimal(None)
check(d3 == Decimal("0"), f"safe_decimal(None) returns 0: {d3}")

# ===================================================================
# 2. TEST: Config
# ===================================================================
print("\n--- 2. Configuration ---")
from src.config import (
    BASE_DIR, INPUT_DIR, SAMPLE_DIR, OUTPUT_DIR, AUDIT_DIR,
    NOTICE_TEMPLATE_PATH, REPORT_TEMPLATE_PATH, init_config
)

# Bootstrap config (normally done by main())
init_config()

check(INPUT_DIR is not None and INPUT_DIR.exists(), f"INPUT_DIR exists: {INPUT_DIR}")
check(SAMPLE_DIR.exists(), f"SAMPLE_DIR exists: {SAMPLE_DIR}")
check(OUTPUT_DIR.exists(), f"OUTPUT_DIR exists: {OUTPUT_DIR}")
check(AUDIT_DIR.exists(), f"AUDIT_DIR exists: {AUDIT_DIR}")
# Templates are non-fatal now; just check they exist or are None
if NOTICE_TEMPLATE_PATH is not None:
    check(NOTICE_TEMPLATE_PATH.exists(), f"NOTICE_TEMPLATE_PATH exists: {NOTICE_TEMPLATE_PATH}")
if REPORT_TEMPLATE_PATH is not None:
    check(REPORT_TEMPLATE_PATH.exists(), f"REPORT_TEMPLATE_PATH exists: {REPORT_TEMPLATE_PATH}")

# ===================================================================
# 3. TEST: Case Discovery
# ===================================================================
print("\n--- 3. Case Discovery ---")
from src.case_discovery import discover_cases, CaseManifest

manifests = discover_cases(INPUT_DIR, NOTICE_TEMPLATE_PATH)
check(len(manifests) >= 1, f"discover_cases found {len(manifests)} case(s)")
m = manifests[0]
check(m.case_id == "CASE_001", f"First case ID: {m.case_id}")
check("Form" in str(m.files.get("form16", "")), f"Form16 file found: {m.files.get('form16', '')}")
check("AIS" in str(m.files.get("ais", "")), f"AIS file found: {m.files.get('ais', '')}")
check("ITR" in str(m.files.get("itr", "")), f"ITR file found: {m.files.get('itr', '')}")
check(len(m.file_hashes) == 3, f"File hashes computed: {len(m.file_hashes)}")
check(m.input_mode == "batch", f"Input mode: {m.input_mode}")

# ===================================================================
# 4. TEST: Extraction
# ===================================================================
print("\n--- 4. Document Extraction ---")
from src.extraction import extract_with_docling, read_docx_fallback, read_xlsx_fallback

form16_extracted = extract_with_docling(Path(m.files["form16"]))
check(form16_extracted is not None, "Form16 extracted")
check("markdown" in form16_extracted, "Form16 has markdown")
check(form16_extracted["extraction_method"] in ("python-docx", "docx-zip-fallback", "pandas-excel"),
      f"Form16 extraction method: {form16_extracted['extraction_method']}")

ais_extracted = extract_with_docling(Path(m.files["ais"]))
check(ais_extracted is not None, "AIS extracted")
check("sheets" in ais_extracted.get("docling_json", {}), "AIS has sheet data")

itr_extracted = extract_with_docling(Path(m.files["itr"]))
check(itr_extracted is not None, "ITR extracted")
check("markdown" in itr_extracted, "ITR has markdown")

# ===================================================================
# 5. TEST: Parsing
# ===================================================================
print("\n--- 5. Text Parsing ---")
from src.parsing import (
    PAN_RE, normalize_assessment_year, clean_name,
    extract_identity_from_table_text, extract_name_pan_ay_from_case_name,
    extract_identity_from_text, first_amount_after_keyword, flatten_text
)

check(PAN_RE.search("ABCPE1234F") is not None, "PAN_RE matches ABCPE1234F")
check(PAN_RE.search("ABCDE1234") is None, "PAN_RE rejects invalid PAN")

ay = normalize_assessment_year("2025-26")
check(ay == "2025-26", f"Normalize AY 2025-26: {ay}")

ay2 = normalize_assessment_year("2025-2026")
check(ay2 == "2025-26", f"Normalize AY 2025-2026: {ay2}")

# Test table extraction
t_name, t_pan, t_ay = extract_identity_from_table_text("PAN | Name | AY | FY\nABCPE1234F | Rajesh | 2025-26 | 2024-25")
check(t_pan == "ABCPE1234F", f"Table extraction PAN: {t_pan}")
check(t_name == "Rajesh", f"Table extraction Name: {t_name}")
check(t_ay == "2025-26", f"Table extraction AY: {t_ay}")

# Test first_amount_after_keyword
amount = first_amount_after_keyword("Gross Salary: 1200000", "gross salary")
check(amount == Decimal("1200000"), f"first_amount_after_keyword: {amount}")

# ===================================================================
# 6. TEST: Mapping
# ===================================================================
print("\n--- 6. Canonical Mapping ---")
from src.mapping import (
    build_canonical_case, map_form16_to_canonical, map_ais_to_canonical,
    map_itr_to_canonical, normalize_key_name
)

check(normalize_key_name("PAN") == "pan", f"normalize_key_name 'PAN': {normalize_key_name('PAN')}")
check(normalize_key_name("Assessment Year") == "assessment year",
      f"normalize_key_name 'Assessment Year': {normalize_key_name('Assessment Year')}")

extracted_docs = {
    "form16": form16_extracted,
    "ais": ais_extracted,
    "itr": itr_extracted,
}

canonical = build_canonical_case(m, extracted_docs)
check(canonical is not None, "build_canonical_case succeeded")
check(canonical.case_id == "CASE_001", f"Canonical case_id: {canonical.case_id}")
check(canonical.identity.pan is not None, f"Identity PAN: {canonical.identity.pan}")
check(canonical.identity.name is not None, f"Identity Name: {canonical.identity.name}")
check(canonical.identity.assessment_year is not None,
      f"Identity AY: {canonical.identity.assessment_year}")
check(canonical.form16.gross_salary > 0, f"Form16 gross_salary: {canonical.form16.gross_salary}")
# Verify at least some AIS financial data was extracted (complex multi-sheet
# Excel may not have all fields, but at least one key field should be >0)
check(
    canonical.ais.salary + canonical.ais.interest + canonical.ais.dividend + canonical.ais.tds > 0,
    f"AIS data check: salary={canonical.ais.salary}, interest={canonical.ais.interest}, dividend={canonical.ais.dividend}, tds={canonical.ais.tds}"
)
check(canonical.itr.salary > 0, f"ITR salary: {canonical.itr.salary}")
check(len(canonical.provenance) > 0, "Provenance populated")

# ===================================================================
# 7. TEST: Validation
# ===================================================================
print("\n--- 7. Validation ---")
from src.validation import validate_tax_case

validation = validate_tax_case(canonical)
check(validation["is_valid"], f"Validation passed: {validation}")

# ===================================================================
# 8. TEST: Discrepancy Engine
# ===================================================================
print("\n--- 8. Discrepancy Engine ---")
from src.discrepancies import (
    reconcile_case, materiality_band, make_discrepancy, Discrepancy
)

band = materiality_band(Decimal("100"))
check(band == "low", f"materiality_band(100): {band}")
band2 = materiality_band(Decimal("100000"))
check(band2 == "high", f"materiality_band(100000): {band2}")

discrepancies = reconcile_case(canonical)
check(len(discrepancies) > 0, f"Found {len(discrepancies)} discrepancy(ies)")
if discrepancies:
    check(discrepancies[0].delta is not None, f"Discrepancy delta present")
    check(discrepancies[0].materiality is not None, f"Materiality: {discrepancies[0].materiality}")

# ===================================================================
# 9. TEST: Decision Composer
# ===================================================================
print("\n--- 9. Decision ---")
from src.decision import compose_decision, DecisionResult

# Use LLM fallback review
from src.llm_reviewer import fallback_llm_review

llm_review = fallback_llm_review(canonical, discrepancies, validation)
decision = compose_decision(discrepancies, llm_review)
check(decision is not None, "Decision composed")
check(decision.decision_type is not None, f"Decision type: {decision.decision_type}")
check(isinstance(decision.is_notice_required, bool), "is_notice_required is boolean")
check(len(decision.reason_codes) > 0, f"Reason codes present: {decision.reason_codes}")

# ===================================================================
# 10. TEST: LLM Reviewer Fallback
# ===================================================================
print("\n--- 10. LLM Reviewer (Fallback) ---")
from src.llm_reviewer import run_vllm_review

review = run_vllm_review(canonical, discrepancies, validation)
check(review is not None, "LLM review returned")
check("case_summary" in review, "Review has case_summary")
check("findings" in review, "Review has findings")
check("investigation_narrative" in review, "Review has investigation_narrative")
check("_fallback_reason" in review, "Review used fallback (LLM not available)")

# ===================================================================
# 11. TEST: Output Packaging
# ===================================================================
print("\n--- 11. Output Packaging ---")
from src.output import write_json, package_case_outputs
from src.document_gen import default_notice_context

context = default_notice_context(canonical, discrepancies, decision)

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    write_json(tmp / "test.json", {"key": "value"})
    check((tmp / "test.json").exists(), "write_json wrote file")

    # Test packaging
    package_case_outputs(
        case_dir=tmp / "output",
        manifest=m,
        canonical_case=canonical,
        validation=validation,
        discrepancies=discrepancies,
        llm_review=review,
        decision=decision,
        generated_files={"test": "test.txt"},
    )
    for fname in ["Case_Summary.json", "Discrepancy_Register.json",
                   "Canonical_Tax_Case.json", "LLM_Review.json", "Audit_Log.json"]:
        fpath = tmp / "output" / fname
        check(fpath.exists(), f"Output file exists: {fname}")

# ===================================================================
# 12. TEST: Document Generation (without docxtpl)
# ===================================================================
print("\n--- 12. Document Generation ---")
from src.document_gen import (
    default_notice_context, render_docx_template, simple_text_render
)

context = default_notice_context(canonical, discrepancies, decision)
check("case_id" in context, "Context has case_id")
check("discrepancies" in context, "Context has discrepancies")

# Test text rendering
rendered = simple_text_render("Hello {{ case_id }}", context)
check("Test" in rendered or context.get("case_id", "")[:3] in rendered,
      f"simple_text_render works: {rendered[:80]}")

# Test DOCX template rendering (should fallback to json since docxtpl is not installed)
with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    render_docx_template(NOTICE_TEMPLATE_PATH, tmp / "Notice.docx", context)
    json_fallback = tmp / "Notice.json"
    check(json_fallback.exists() or (tmp / "Notice.docx").exists(),
          "DOCX rendering produced output (JSON fallback or DOCX)")

# ===================================================================
# 13. TEST: Main Pipeline (dry-run)
# ===================================================================
print("\n--- 13. Main Pipeline (dry-run) ---")
import subprocess
result = subprocess.run(
    [sys.executable, "main.py", "--dry-run"],
    capture_output=True, text=True, timeout=30
)
check(result.returncode == 0, f"main.py --dry-run exit code: {result.returncode}")
check("CASE_001" in result.stdout or "Found" in result.stdout,
      f"Dry-run output contains case info: {result.stdout[:200]}")

# ===================================================================
# 14. TEST: Full Process (single case)
# ===================================================================
print("\n--- 14. Full Pipeline (single case) ---")
result2 = subprocess.run(
    [sys.executable, "main.py", "--case", "CASE_001"],
    capture_output=True, text=True, timeout=60
)
stdout = result2.stdout
stderr = result2.stderr
check(result2.returncode == 0,
      f"Full pipeline exit code: {result2.returncode}")
check("CASE_001" in stdout or "Decision" in stdout or "successfully" in stdout,
      f"Pipeline output: {stdout[-300:]}")

# Check output directory was created
output_dirs = list(OUTPUT_DIR.glob("*"))
has_output = len(output_dirs) > 0 and any(d.is_dir() for d in output_dirs)
check(has_output, f"Output directory created: {[d.name for d in output_dirs[:3]]}")

# ===================================================================
# SUMMARY
# ===================================================================
print("\n" + "=" * 70)
if errors:
    print(f"RESULTS: {len(errors)} test(s) FAILED")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("RESULTS: All tests PASSED!")
    print("=" * 70)
    sys.exit(0)
