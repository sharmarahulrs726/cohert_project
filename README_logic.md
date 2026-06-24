# Tax Investigation System

An **LLM-powered tax compliance analysis system** that automates the discovery,
extraction, reconciliation, and forensic review of discrepancies between tax
documents (Form 16, AIS, ITR Extract) for Indian Income Tax assessments.

The LLM receives **raw sheet-by-sheet data** from every XLSX file alongside
pre-computed discrepancies, enabling independent forensic verification and
identifying issues beyond rule-based detection.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Directory Structure](#directory-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Pipeline Stages](#pipeline-stages)
- [Output Files](#output-files)
- [data_extraction.json](#data_extractionjson)
- [LLM Review Flow](#llm-review-flow)
- [Centralized Prompt Management](#centralized-prompt-management)
- [Discrepancy Rules](#discrepancy-rules)
- [Launcher Scripts](#launcher-scripts)
- [Development](#development)

---

## Overview

This system processes taxpayer case files (Form 16, AIS, ITR Extract) and:

1. **Extracts** structured data from every sheet of every XLSX/DOCX file
2. **Identifies** taxpayer identity (PAN, Name, Assessment Year) via multi-strategy parsing
3. **Validates** data quality and flags missing or unusual values
4. **Reconciles** rule-based discrepancies between source documents and ITR
5. **Reviews** using an LLM that receives both pre-computed discrepancies AND raw
   extracted documents for forensic cross-referencing
6. **Outputs** validation steps with responsible parties, document requests, and legal basis
7. **Generates** DOCX reports and notices from Jinja2 templates
8. **Packages** all outputs as structured JSON + DOCX/PDF

---

## Architecture

```
main.py                              # CLI entry point / orchestration
├── src/
│   ├── config.py                    # Paths, constants, template detection
│   ├── utils.py                     # Shared helpers (hashing, decimals, imports)
│   ├── models.py                    # Pydantic data models (CanonicalTaxCase, etc.)
│   ├── prompts.py                   # ⭐ Centralized prompt registry (single source of truth)
│   ├── case_discovery.py            # CaseManifest & discover_cases()
│   ├── extraction.py                # Document extraction (all sheets from XLSX)
│   ├── parsing.py                   # PAN/Name/AY regex & table parsing
│   ├── mapping.py                   # Raw extraction -> canonical models
│   ├── validation.py                # Data quality validation
│   ├── discrepancies.py             # Discrepancy engine (rule-based)
│   ├── llm_reviewer.py              # LLM forensic review (prompts from prompts.py)
│   ├── decision.py                  # Decision composer (notice / report)
│   ├── document_gen.py              # DOCX template rendering + PDF conversion
│   └── output.py                    # JSON output packaging (incl. data_extraction.json)
├── input/                           # Place input case files here
├── sample/                          # Place report/notice DOCX templates here
├── output/                          # Generated outputs (auto-created)
├── requirements.txt
├── run.sh                           # Linux/macOS launcher
└── run.bat                          # Windows launcher
```

### Prompt Management Layer

```
src/prompts.py              ← ALL prompts (single source of truth)
        ↓
src/llm_reviewer.py         ← orchestration only (no hardcoded prompt text)
        ↓
LangChain (ChatOpenAI / ChatOllama)
        ↓
OpenRouter / vLLM / Ollama  ← LLM provider
```

---

## Prerequisites

### Python
- Python 3.11
-py -3.11 -m venv .venv
- pip

### No system dependencies required
PDF generation uses a **pure Python fallback** (`fpdf2`) -- no LibreOffice,
Microsoft Word, or any system tool needed.

- **LibreOffice** (optional) -- DOCX to PDF via headless LibreOffice if installed.
- **docx2pdf** (optional) -- PDF via Microsoft Word COM on Windows if installed.
- **fpdf2** (built-in) -- pure Python PDF generation. Auto-downloads DejaVuSans
  Unicode font on first use if no system font found.

The system tries all three methods in order and always falls back to the
Python-only solution.

### LLM Provider (recommended for full capabilities)

The system uses **LangChain** (`ChatOpenAI` / `ChatOllama`) to connect to any OpenAI-compatible endpoint:

| Provider | URL | Auth |
|----------|-----|------|
| **OpenRouter** (default) | `https://openrouter.ai/api/v1` | `OPENAI_API_KEY` (API key required) |
| **vLLM** | `http://localhost:8000/v1` | None (local) |
| **Ollama** | `http://localhost:11434` | None (local) |
| **OpenAI** | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| **Custom** | Any OpenAI-compatible endpoint | As required |

If no LLM is available, the system falls back to deterministic rule-based analysis.

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd cohert_project2

# 2. Create and activate a virtual environment (recommended)
py -3.11 -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Prepare input files
#    Place case files in input/ (see Input Structure below)
```

### Quick start with launcher scripts  (or run py main.py)

```bash
# Linux/macOS
chmod +x run.sh
./run.sh

# Windows
run.bat
```

Launcher scripts auto-detect `uv` (fast) or fall back to pip + `.venv`.
Requires Python 3.11+.

---

## Directory Structure

### Input Structure

The system supports **two modes** (do not mix both in the same input directory):

#### Single-case mode
Place all three files directly in `input/`:

```
input/
├── Form16.docx              # (or .xlsx)
├── AIS.xlsx                 # (or .docx)
└── ITR_Extract.docx         # (or .xlsx)
```

#### Batch mode (recommended for multiple persons)
Create one subfolder per case. Each folder must contain **3 files**:

```
input/
├── Person1_Rahul_ABCDE1234F/
│   ├── Form_16.xlsx
│   ├── AIS.xlsx
│   └── ITR_extract.xlsx
├── Person2_Priya_FGHI5678J/
│   ├── Form_16.xlsx
│   ├── AIS.xlsx
│   └── ITR_extract.xlsx
└── ...
```

**File name matching is flexible** -- the following patterns are recognized:

| Required File | Accepted Names |
|---------------|----------------|
| **Form 16** | `Form16.docx/xlsx`, `Form 16.docx/xlsx`, `form16.docx/xlsx`, `Form_16.xlsx`, `form_16.docx/xlsx` |
| **AIS** | `AIS.docx/xlsx`, `ais.docx/xlsx` |
| **ITR Extract** | `ITR_Extract.docx/xlsx`, `ITR Extract.docx/xlsx`, `itr_extract.docx/xlsx`, `ITR.docx/xlsx` |

### Templates

Place DOCX templates in `sample/`:

- **Notice template**: `Notice_Template.docx` (or `notice.docx`, `Notice u.s 133(6).docx`)
- **Report template**: `Tax_Investigation_Report_Template.docx` (or `REPORT_TEMPLATE.docx`)

Templates use Jinja2-style `{{ placeholders }}` for dynamic content. Available
context variables include `assessee_name`, `pan`, `assessment_year`,
`financial_year`, `discrepancies_block`, `llm_review`, etc.

---

## Configuration

### LLM Configuration (Runtime-Evaluated)

LLM settings are fetched at runtime via `get_llm_config(force_reload=False)` in `src/config.py`.
This means environment changes take effect on each call **without restarting Python**.

| Setting | Env Var (priority order) | Default | Description |
|---------|--------------------------|---------|-------------|
| Base URL | `LLM_BASE_URL` > `VLLM_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint |
| API Key | `OPENAI_API_KEY` > `ONLINE_LLM_KEY` > `VLLM_API_KEY` | `None` | Authentication token |
| Model | `LLM_MODEL` > `VLLM_MODEL_NAME` | `qwen/qwen3.5-9b` | Model name |

**Provider auto-detection** inspects the base URL:

| URL pattern | Provider | Default behavior |
|-------------|----------|-----------------|
| `openrouter` | OpenRouter | Requires valid API key |
| `openai` | OpenAI | Requires valid API key |
| `localhost:8000` | vLLM | Dummy key `"dummy"` |
| `localhost:11434` | Ollama | Key set to `"ollama"`, auto-appends `/v1` |
| Other | Custom | Requires user-supplied key |

**Example `.env` file:**

```env
# OpenRouter (default)
OPENAI_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Or override with explicit settings
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3.5-9b

# For local Ollama:
# LLM_BASE_URL=http://localhost:11434/v1
```

### Legacy Backwards-Compat Constants

The module also provides once-evaluated constants at import time:

| Constant | Default |
|----------|---------|
| `VLLM_BASE_URL` | `https://openrouter.ai/api/v1` |
| `MODEL_NAME` | `qwen/qwen3.5-9b` |
| `VLLM_API_KEY` | From env |

These are kept for callers that import at module level; `get_llm_config()` is preferred.

### Template Configuration

Templates are auto-detected from `sample/` in this priority order:

| Template | Search Order |
|----------|-------------|
| Notice | `Notice_Template.docx` -> `notice.docx` -> `Notice u.s 133(6).docx` |
| Report | `input/REPORT_TEMPLATE.docx` -> `sample/Tax_Investigation_Report_Template.docx` -> `sample/REPORT_TEMPLATE.docx` -> `sample/report.docx` |

### Other Settings

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| LibreOffice | `LIBREOFFICE_CMD` | `soffice` (Win) / `libreoffice` (Linux) | PDF conversion binary |

### Template auto-detection

Templates are auto-detected from `sample/` in this priority order:

| Template | Search Order |
|----------|-------------|
| Notice | `Notice_Template.docx` -> `notice.docx` -> `Notice u.s 133(6).docx` |
| Report | `input/REPORT_TEMPLATE.docx` -> `sample/Tax_Investigation_Report_Template.docx` -> `sample/REPORT_TEMPLATE.docx` -> `sample/report.docx` |

---

## Usage

```bash
# Process all discovered cases
python main.py

# Dry-run -- list cases without processing
python main.py --dry-run

# Process a single case by ID
python main.py --case CASE_001

# Process multiple specific cases
python main.py --case CASE_001 --case CASE_005 --case CASE_011

# Use a custom input directory
python main.py --input /path/to/cases

# Using launcher scripts (auto-installs dependencies)
./run.sh              # Linux/macOS
run.bat               # Windows
./run.sh --dry-run    # With arguments
```

---

## Pipeline Stages

| Stage | Module | Description |
|-------|--------|-------------|
| 1. Discovery | `case_discovery.py` | Scans input directory; builds manifests |
| 2. Extraction | `extraction.py` | Extracts ALL sheets from XLSX, all text from DOCX |
| 3. Canonical Mapping | `mapping.py` | Maps raw data to Pydantic models |
| 4. Identity Resolution | `mapping.py` | Multi-strategy PAN/Name/AY extraction |
| 5. Validation | `validation.py` | Checks completeness and data quality |
| 6. Discrepancy Analysis | `discrepancies.py` | Rule-based source vs. ITR comparison |
| 7. LLM Forensic Review | `llm_reviewer.py` | LLM analyzes both pre-computed discrepancies AND raw sheet data |
| 8. Decision | `decision.py` | Notice candidate / report-only / no-action |
| 9. Document Generation | `document_gen.py` | Renders DOCX from Jinja2 templates + PDF |
| 10. Output Packaging | `output.py` | Writes JSON audit trail + data_extraction.json |

### Stage 2: Full-Sheet Extraction

For XLSX files, **every sheet** is extracted with full row/column data:

| Document | Typical Sheets |
|----------|---------------|
| **AIS.xlsx** | Summary, Part A - TDS Summary, Part A2 Property, Part C Tax Paid, Part E SFT |
| **Form_16.xlsx** | Sheet1 (quarterly salary/TDS breakdown) |
| **ITR_extract.xlsx** | Part A- General Details, Salary, House Property, Other Sources, Deductions, TDS and Bank details, SCH TI |

Each sheet's data is stored as:
- `docling_json.sheets[sheet_name]` -- list of row dicts (column: value)
- `markdown` -- pipe-delimited text representation of all sheets

This raw data is saved to `data_extraction.json` AND passed to the LLM for
forensic analysis.

### Stage 7: LLM Forensic Review

The LLM receives a structured payload containing:

```json
{
  "canonical_case": { "identity": {...}, "form16": {...}, "ais": {...}, "itr": {...} },
  "validation": { "is_valid": true, "issues": [] },
  "precomputed_discrepancies": [ { "category": "salary", "delta": "...", ... } ],
  "raw_extracted_documents": {
    "form16": { "docling_json": { "sheets": {...} }, "markdown": "..." },
    "ais":    { "docling_json": { "sheets": {...} }, "markdown": "..." },
    "itr":    { "docling_json": { "sheets": {...} }, "markdown": "..." }
  }
}
```

The LLM is instructed to:

1. **Cross-reference** each pre-computed discrepancy against raw sheets
2. **Identify additional** discrepancies not caught by rules (property income,
   TDS quarterly mismatches, SFT inconsistencies, deduction anomalies)
3. **Assess materiality** per IT Act thresholds (50K general, 1L bank deposits)
4. **Recommend validation steps** with responsible party, document requests,
   and legal basis

Output schema requires four sections: `case_summary`, `findings`,
`investigation_narrative`, and `validation_steps`.

When vLLM is unavailable, the deterministic fallback generates the same
schema using rule-based logic.

---

## Output Files

For each case processed, output is written to `output/<Name_PAN_Timestamp>/`:

```
output/
└── Rahul_Sharma_ABCDE1234F_20260613_113640/
    ├── Case_Summary.json                  # Decision overview
    ├── Canonical_Tax_Case.json            # Structured case data
    ├── Discrepancy_Register.json          # Rule-based discrepancies
    ├── LLM_Review.json                    # LLM forensic analysis + validation_steps
    ├── data_extraction.json               # Full raw data from ALL sheets
    ├── Audit_Log.json                     # Full provenance + decisions
    ├── Tax_Investigation_Report.docx      # Report (always generated)
    ├── Tax_Investigation_Report.pdf       # PDF via fpdf2 (always generated)
    └── Notice.docx / Notice.pdf           # Notice (only when discrepancies trigger)
```

### Output rules

| Scenario | Report | Notice |
|----------|--------|--------|
| No discrepancies | DOCX + PDF | -- |
| Minor discrepancies | DOCX + PDF | -- |
| Notice-triggering discrepancies | DOCX + PDF | DOCX + PDF |

### PDF conversion fallback chain

1. **LibreOffice** (headless) -- best quality, cross-platform
2. **docx2pdf** (Microsoft Word COM) -- Windows native
3. **fpdf2** (pure Python) -- always works, auto-downloads Unicode font

---

## data_extraction.json

This file contains the **complete raw extracted data** from every document.
It is generated in each case's output folder and used by the LLM for
forensic analysis.

### Schema

```json
{
  "form16": {
    "file_name": "Form_16.xlsx",
    "source_path": "C:\\...\\Form_16.xlsx",
    "extracted_at": "2026-06-13T04:03:12Z",
    "extraction_method": "pandas-excel",
    "docling_json": {
      "sheets": {
        "Sheet1": [
          { "Column1": "value", "Column2": "value", ... },
          ...
        ]
      }
    },
    "markdown": "# Sheet: Sheet1\nCol1 | Col2 | ...\nval1 | val2 | ...\n..."
  },
  "ais": {
    "file_name": "AIS.xlsx",
    "extraction_method": "pandas-excel",
    "docling_json": {
      "sheets": {
        "Summary": [ { "PAN": "...", "Name": "...", "AY": "...", "FY": "..." } ],
        "Part A - TDS Summary": [ { "Deductor": "...", "Income": "...", "TDS": "..." }, ... ],
        "Part A2 Property": [ { "Transaction": "...", "Amount": "...", "TDS": "..." } ],
        "Part C Tax Paid": [ { "Description": "...", "Amount": "..." } ],
        "Part E SFT": [ { "Description": "...", "Amount": "..." }, ... ]
      }
    },
    "markdown": "..."
  },
  "itr": {
    "file_name": "ITR_extract.xlsx",
    "extraction_method": "pandas-excel",
    "docling_json": {
      "sheets": {
        "Part A- General Details": [ ... ],
        "Salary": [ ... ],
        "House Property": [ ... ],
        "Other Sources": [ ... ],
        "Deductions": [ ... ],
        "TDS and Bank details": [ ... ],
        "SCH TI": [ ... ]
      }
    },
    "markdown": "..."
  }
}
```

### Example: AIS sheets for Rahul Sharma

| Sheet | Rows | Content |
|-------|------|---------|
| Summary | 1 | PAN, Name, AY, FY |
| Part A - TDS Summary | 3 | Deductor name, gross income, TDS deducted |
| Part A2 Property | 1 | Property transaction details |
| Part C Tax Paid | 1 | Tax payment summary |
| Part E SFT | 2 | SFT transaction entries (deposits, time deposits) |

The LLM uses this data to verify that TDS credits in AIS match Form 16
quarters, that SFT deposits are disclosed in ITR, and that property
transactions are consistent across documents.

---

## LLM Review Flow

```
extracted_docs (all sheets)
        │
        ├──> data_extraction.json (saved to output)
        │
        └──> build_llm_messages()
                │
                ├── canonical_case (structured fields)
                ├── validation (data quality issues)
                ├── precomputed_discrepancies (from discrepancies.py)
                └── raw_extracted_documents (full markdown + sheets)
                        │
                        ▼
               build_investigation_messages()   ← src/prompts.py
                        │
                        ▼
                _create_chat_model()             ← src/llm_reviewer.py (uses get_llm_config())
                        │
                        ▼
                LangChain ChatOpenAI / ChatOllama
                        │
                        ▼
                OpenRouter / vLLM / Ollama or deterministic fallback
                        │
                        ▼
                LLM_Review.json
                ├── case_summary (risk level, counts)
                ├── findings (confirmed/probable/uncertain + sheet_references)
                ├── investigation_narrative (facts, issues, next step)
                └── validation_steps (document requests, legal basis)
```

### LLM Output Schema

| Section | Fields |
|---------|--------|
| `case_summary` | `overall_risk`, `material_discrepancy_count`, `manual_review_required`, `notice_candidate`, `summary_text` |
| `findings[]` | `finding_id`, `category`, `status`, `materiality`, `difference_summary`, `reasoning`, `source_support`, `sheet_references`, `manual_review_required` |
| `investigation_narrative` | `facts_established[]`, `issues_observed[]`, `uncertainties[]`, `recommended_next_step` |
| `validation_steps[]` | `step_id`, `description`, `priority`, `responsible_party`, `document_requested`, `legal_basis` |

### Validation Steps (fallback example)

```json
[
  {
    "step_id": "VS-001",
    "description": "Issue notice under Section 133(6) calling for books of accounts...",
    "priority": "high",
    "responsible_party": "assessee",
    "document_requested": "Books of accounts, bank statements, property documents, TDS certificates",
    "legal_basis": "Section 133(6) of Income Tax Act, 1961"
  },
  {
    "step_id": "VS-002",
    "description": "Verify TDS credits with deductors and cross-check with TRACES",
    "priority": "high",
    "responsible_party": "deductor",
    "document_requested": "TDS certificates, Form 26AS/TRACES statement",
    "legal_basis": "Section 203AA read with Rule 31AB"
  }
]
```

Responsible parties: `assessee`, `deductor`, `bank`, `registry`, `third_party`.

---

## Centralized Prompt Management

The system uses an enterprise-grade **3-layer prompt architecture**:

```
src/prompts.py              ← ALL prompts (single source of truth)
        ↓
src/llm_reviewer.py         ← orchestration only (no hardcoded prompt text)
        ↓
LangChain (ChatOpenAI / ChatOllama)
        ↓
OpenRouter / vLLM / Ollama  ← LLM provider
```

### What Changed

| Before (BAD) | After (CLEAN) |
|--------------|---------------|
| Prompts hardcoded inline in `llm_reviewer.py` | All prompts in `src/prompts.py` |
| System prompt duplicated & overwritten in `run_vllm_review()` | Single definition via `build_investigation_messages()` |
| Raw dict message construction | LangChain `SystemMessage` / `HumanMessage` |
| Direct OpenAI SDK + httpx calls | LangChain `ChatOpenAI` / `ChatOllama` unified interface |
| Static import-time config | Runtime `get_llm_config()` reads `.env` per call |
| Difficult to tune without touching code | Edit `prompts.py` with zero code risk |

### Prompt Registry (`src/prompts.py`)

| Constant | Purpose |
|----------|---------|
| `INVESTIGATION_SYSTEM_PROMPT` | Forensic tax officer persona with full analysis instructions |
| `STRICT_JSON_ENFORCER` | JSON-only output enforcer with schema definition |
| `build_investigation_messages(user_prompt)` | Returns OpenAI-ready `[{role, content}]` dicts |

### Benefits

- **Easy prompt tuning** — edit `prompts.py` without touching business logic
- **Cleaner LLM pipeline** — no duplicated or overwritten system prompts
- **Production-safe** — no accidental prompt override bugs
- **Extensible** — ready for A/B testing, versioning (v1/v2 prompts), experiment tracking

---

## Discrepancy Rules

The system compares these fields between source documents (Form 16 / AIS) and ITR:

| Category | Source | Target |
|----------|--------|--------|
| `salary` | AIS salary (or Form 16 gross) | ITR salary |
| `tds` | AIS TDS (or Form 16 TDS) | ITR TDS |
| `interest` | AIS interest | ITR interest |
| `dividend` | AIS dividend | ITR dividend |
| `securities` | AIS securities | ITR securities |
| `bank_deposits_vs_total_income` | AIS bank deposits | ITR total income |

**Notice triggers:**
- Delta > 50,000 for any category (general)
- Delta > 1,00,000 for `bank_deposits_vs_total_income`

**Materiality bands:**
- **Low**: 1 -- 1,000
- **Medium**: 1,001 -- 50,000
- **High**: > 50,000

---

## Launcher Scripts

### run.sh (Linux/macOS)

- Checks for Python 3.11+ (both major and minor version)
- Installs dependencies via `uv` (if available) or pip + `.venv`
- Forwards all arguments to `main.py`

### run.bat (Windows)

- Uses `setlocal enabledelayedexpansion` for correct variable expansion
- Checks for Python 3.11+ via `python` or `py` launcher
- Installs dependencies via `uv` (if available) or pip + `.venv`
- Forwards all arguments to `main.py`

Both scripts auto-create a virtual environment if needed and handle the full
dependency installation pipeline.

---

## Development

### Project structure conventions

- All business logic lives in `src/` as independent modules
- `main.py` is the thin orchestration layer (easy to modify/repurpose)
- Each module has a single responsibility
- Use `asdict()` from `dataclasses` for serialization
- Use `model_dump_json()` / `model_dump()` from Pydantic models

### Adding a new discrepancy rule

1. Open `src/discrepancies.py`
2. Add a tuple to the `rules` list in `reconcile_case()`:

```python
("my_new_rule", c.ais.some_field, c.itr.some_field, "Description of the rule.")
```

### Testing

```bash
# Run a dry-run to verify case discovery
python main.py --dry-run

# Process the first case only
python main.py --case CASE_001
```

---

## License

This project is provided for educational and professional tax analysis purposes.
