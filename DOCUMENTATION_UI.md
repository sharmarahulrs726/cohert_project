# Tax Investigation System — Technical Documentation

```
System: LLM-powered tax compliance analysis
Frontend: React 19 + TypeScript + Vite 6 + Tailwind CSS 3
Backend:  Python 3.11 + FastAPI + LangChain
Pipeline: Extraction → Mapping → Validation → Discrepancies → LLM Review → Decision → Document Gen
```

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Frontend Architecture](#2-frontend-architecture)
3. [Backend API](#3-backend-api)
4. [Pipeline Stages](#4-pipeline-stages)
5. [LLM Integration](#5-llm-integration)
6. [File Logging](#6-file-logging)
7. [Data Flow](#7-data-flow)
8. [API Endpoint Reference](#8-api-endpoint-reference)
9. [Error Handling & Fallbacks](#9-error-handling--fallbacks)

---

## 1. Architecture Overview

```
┌─────────────┐     Vite Proxy      ┌──────────────┐
│   Browser   │ ──── /api/* ──────→ │  FastAPI      │
│  :5173      │ ←────────────────── │  :8000        │
└─────────────┘                     └──────┬───────┘
                                           │
                                    ┌──────┴───────┐
                                    │  Case         │
                                    │  Processor    │
                                    │  (background  │
                                    │   thread)     │
                                    └──────┬───────┘
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              │                            │                            │
         ┌────┴─────┐              ┌───────┴───────┐           ┌───────┴───────┐
         │  src/    │              │  LLM Provider │           │  Template     │
         │ Pipeline │              │  (OpenRouter) │           │  Files (DOCX) │
         └──────────┘              └───────────────┘           └───────────────┘
```

**Communication pattern:**
- Frontend polls `/api/session/{id}/progress` every 2 seconds after starting a process
- Backend runs the full pipeline in a **daemon thread** (non-blocking)
- Logs are captured in-memory (`CAPTURED_LOGS`) for frontend streaming AND written to disk (`logs/api_log_*.log`)

---

## 2. Frontend Architecture

### 2.1 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 19.0 |
| Language | TypeScript | 5.5 |
| Bundler | Vite | 6.0 |
| HTTP Client | Axios | 1.7 |
| Styling | Tailwind CSS | 3.4 |
| Built-in | PostCSS, Autoprefixer | — |

### 2.2 Component Tree

```
App.tsx  (step router: upload → processing → report → notice_review → notice_generated → complete)
├── ErrorBoundary.tsx         — Catches render errors, shows reload button
├── FileUpload.tsx            — Three drag-and-drop slots (Form16, AIS, ITR)
├── ProcessingScreen.tsx      — Progress bar + live log stream
├── ReportViewer.tsx          — Accordion report with summary, discrepancies, LLM findings, validation steps
├── NoticeReview.tsx          — Notice preview + generate/skip decision
└── NoticeViewer.tsx          — DOCX/PDF download + inline PDF preview
```

### 2.3 State Management (`useCaseProcessing.ts`)

The custom hook `useCaseProcessing()` manages all application state:

| State | Type | Purpose |
|-------|------|---------|
| `step` | `AppStep` | Current UI step: `upload \| processing \| report \| notice_review \| notice_generated \| complete` |
| `sessionId` | `string \| null` | Active session UUID |
| `uploadedFiles` | `Record<string, File>` | Files by type (`form16`, `ais`, `itr`) |
| `processingMessages` | `string[]` | Live log messages from backend |
| `progress` | `ProgressData \| null` | Polled progress from `/progress` endpoint |
| `reportData` | `ReportData \| null` | Full report after processing |
| `error` | `string \| null` | Error message to display |

**Polling mechanism:**
```
startProcessing() called
    ↓
_startPolling(sessionId)
    ↓
setInterval(2000ms) {
    GET /api/session/{id}/progress
        ↓
    if result_ready → fetch /api/session/{id}/report → setStep('report')
    if error        → display error, return to upload
    if timeout (600s) → display timeout error
}
```

### 2.4 TypeScript Types (`types/index.ts`)

Key interfaces:

```typescript
interface ProgressData {
  step: string;
  progress: number;        // 0–100
  message: string;
  error?: string | null;
  result_ready?: boolean;
  logs?: string[];         // Incremental log messages
  log_offset?: number;
}

interface ReportData {
  case_summary: Record<string, unknown>;
  canonical_case: Record<string, unknown>;
  discrepancies: Record<string, unknown>[];   // Rule-based discrepancy table
  llm_review: Record<string, unknown>;         // LLM findings or fallback
  decision_type: string;                        // NOTICE_AND_REPORT | REPORT_ONLY | NO_DISCREPANCY
  is_notice_required: boolean;
  summary_cards: CaseSummaryCard;               // Risk, findings count, material count
  generated_files: Record<string, string>;      // Output file paths
}

interface CaseSummaryCard {
  risk_level: string;           // low | medium | high
  findings_count: number;
  notice_candidate: boolean;
  material_discrepancy_count: number;
}

type AppStep = 'upload' | 'processing' | 'report' | 'notice_review' | 'notice_generated' | 'complete';
```

---

## 3. Backend API

### 3.1 FastAPI Application (`api/main.py`)

**Initialization sequence:**
```
1. logging.basicConfig()          — Console logging
2. File handler setup             — Creates logs/api_log_{timestamp}.log, captures ALL modules
3. init_config()                  — Detects input dirs, templates
4. CORSMiddleware                 — Allows :5173 origins
5. Startup event                  — Creates api/input/, api/output/
```

**Configuration (`src/config.py`):**

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Always absolute
ENV_PATH = PROJECT_ROOT / ".env"

def get_llm_config(force_reload=True) -> dict:
    load_dotenv(ENV_PATH, override=True)   # Always fresh from file
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("VLLM_BASE_URL") or "https://openrouter.ai/api/v1"
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ONLINE_LLM_KEY") or os.getenv("VLLM_API_KEY")
    model = os.getenv("LLM_MODEL") or os.getenv("VLLM_MODEL_NAME") or "qwen/qwen3.5-9b"
```

Key features:
- `load_dotenv()` uses **absolute path** — works regardless of working directory
- `override=True` — reloads `.env` on every call
- Default model fallback ensures `ChatOpenAI(model=...)` never receives `None`

### 3.2 Case Processor (`api/services/case_processor.py`)

**Session management:**
- `create_session()` — UUID session, creates `api/input/{id}/` and `api/output/{id}/`
- Sessions stored on filesystem (no database)

**Log capture:**
- `LogCaptureHandler` — custom logging handler added to root logger
- Captures all logs (from `api.*` and `src.*` modules) into `CAPTURED_LOGS` list
- Frontend polls `/progress` to receive incremental log chunks via `log_offset`

---

## 4. Pipeline Stages

The pipeline runs in a background daemon thread after `POST /api/session/{id}/process`.

```
Stage 1: EXTRACTING     (progress 10%)
  ↓
Stage 2: MAPPING        (progress 25%)
  ↓
Stage 3: VALIDATING     (progress 35%)
  ↓
Stage 4: DISCREPANCIES  (progress 45%)
  ↓
Stage 5: LLM_REVIEW     (progress 55%)
  ↓
Stage 6: DECISION        (progress 70%)
  ↓
Stage 7: REPORT_GEN     (progress 75%)
  ↓
Stage 8: NOTICE_GEN     (progress 80%)
  ↓
Stage 9: PACKAGING      (progress 95%)
  ↓
Stage 10: COMPLETE      (progress 100%)
```

### Stage 1 — Extraction (`src/extraction.py`)

Reads XLSX and DOCX files:

- **XLSX**: Reads all sheets via `pandas.read_excel()` or `docling`, extracts every cell
- **DOCX**: Reads paragraphs and tables via `python-docx`, falls back to raw XML parsing
- Output: `Dict[str, Any]` per document with `markdown` (text) and `docling_json` (structured)

### Stage 2 — Mapping (`src/mapping.py`)

Converts raw extracted text into canonical Pydantic models:

- `Form16Data` — salário bruto, TDS descontado, deduções Chapter VI-A
- `AISData` — salário, juros, dividendos, TDS, transações SFT
- `ITRData` — salário, juros, dividendos, TDS, renda total
- `TaxpayerIdentity` — PAN, nome, ano de avaliação (multi-strategy regex extraction)

Multi-strategy identity parsing:
1. Structured JSON rows from docling
2. Vertical key-value layout detection
3. Blob text regex parsing
4. Direct AIS file cell inspection via openpyxl

### Stage 3 — Validation (`src/validation.py`)

Checks:
- PAN presence
- Assessment year presence
- Negative amount detection on all numeric fields

Returns: `{ "is_valid": bool, "issues": string[] }`

### Stage 4 — Discrepancies (`src/discrepancies.py`)

Rule-based comparison engine. Compares each source document value against declared ITR value.

**Materiality thresholds (Indian Tax Law):**
| Category | Threshold |
|----------|-----------|
| General (salary, TDS, interest, dividend, securities) | ₹50,000 |
| Bank deposits vs total income | ₹1,00,000 |

**Discrepancy fields compared:**
- Form 16 Gross Salary vs ITR Salary
- Form 16 TDS vs ITR TDS
- AIS Salary vs ITR Salary
- AIS Interest vs ITR Interest
- AIS Dividend vs ITR Dividend
- AIS TDS vs ITR TDS
- Bank Deposits vs Total Income

Output: `List[Discrepancy]` where each has `discrepancy_id, category, delta, materiality, notice_candidate, reason`.

### Stage 5 — LLM Review (`src/llm_reviewer.py`)

Two-attempt strategy:
1. **Attempt 1**: `ChatOpenAI` with `response_format={"type": "json_object"}` for structured JSON output
2. **Attempt 2** (fallback): Same model without JSON format binding

**Model creation:**
```python
ChatOpenAI(
    model=resolved_model,
    base_url=base_url + "/v1",
    api_key=api_key,
    temperature=0.1,
    max_retries=2,
    request_timeout=300,    # 5 minutes
)
```

**Provider auto-detection:**
| URL pattern | Provider | Auth |
|-------------|----------|------|
| `openrouter` | OpenRouter | API key required |
| `openai` | OpenAI | API key required |
| `localhost:8000` or `vllm` | vLLM | None (dummy key) |
| `localhost:11434` | Ollama | None (ollama key) |

**Fallback** (`fallback_llm_review()`):
When LLM fails, a deterministic rule-based review produces the same JSON schema using:
- Materiality-based risk assessment
- Converts `Discrepancy` objects into findings
- Generates hardcoded validation steps per Indian Tax Law

### Stage 6 — Decision (`src/decision.py`)

Cross-validates LLM output against rule-based discrepancies:

```
LLM says notice + rules agree       → NOTICE_AND_REPORT
LLM says notice + rules disagree    → overridden, REPORT_ONLY (code: LLM_NOTICE_OVERRIDDEN_NO_THRESHOLD)
LLM says no notice + rules agree    → REPORT_ONLY
LLM unavailable                     → rule-based only
No discrepancies                    → NO_DISCREPANCY
```

### Stage 7 — Document Generation (`src/document_gen.py`)

- Renders Jinja2-style DOCX templates with case data
- Converts DOCX to PDF via LibreOffice (headless) → python-docx → fpdf2 fallback chain
- Multi-method PDF generation (tries 3 approaches in sequence)

### Stage 8 — Output Packaging (`src/output.py`)

Writes to `api/output/{session_id}/`:
| File | Content |
|------|---------|
| `Case_Summary.json` | Decision + summary |
| `Canonical_Tax_Case.json` | Normalized taxpayer data |
| `Discrepancy_Register.json` | All discrepancies found |
| `LLM_Review.json` | LLM analysis (or fallback) |
| `Tax_Investigation_Report.docx/pdf` | Generated report |
| `Notice.docx/pdf` | Generated notice (if applicable) |
| `data_extraction.json` | Raw extracted document data |

---

## 5. LLM Integration

### 5.1 Prompt Architecture (`src/prompts.py`)

**Two-part system prompt:**
1. `INVESTIGATION_SYSTEM_PROMPT` — Senior Indian Income Tax Officer persona with forensic analysis instructions
2. `STRICT_JSON_ENFORCER` — JSON-only output enforcement with full schema definition

**User prompt** includes:
- Canonical case data (PAN, name, AY, amounts)
- Pre-computed discrepancies (from rule engine)
- Validation issues
- Raw extracted documents (capped at 15K chars per file)

### 5.2 JSON Output Schema

```json
{
  "case_summary": {
    "overall_risk": "low|medium|high",
    "material_discrepancy_count": 0,
    "manual_review_required": true,
    "notice_candidate": true,
    "summary_text": "string"
  },
  "findings": [{ "finding_id": "", "category": "", "status": "", "materiality": "", ... }],
  "investigation_narrative": {
    "facts_established": [],
    "issues_observed": [],
    "uncertainties": [],
    "recommended_next_step": "no_action|manual_review|issue_notice"
  },
  "validation_steps": [{ "step_id": "", "description": "", "priority": "", "responsible_party": "", ... }]
}
```

### 5.3 Retry & Fallback Chain

```
LLM Call
  ├── Attempt 1: response_format=json_object
  │     └── Fail → log warning
  ├── Attempt 2: no format binding
  │     └── Fail → raise exception
  └── Exception caught at run_vllm_review()
        └── fallback_llm_review() — deterministic rule-based output
```

---

## 6. File Logging

### 6.1 Setup (`api/main.py`)

```python
log_dir = PROJECT_ROOT / "logs"
log_dir.mkdir(exist_ok=True)
log_filename = log_dir / f"api_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
_file_handler = logging.FileHandler(str(log_filename), encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
logging.getLogger().addHandler(_file_handler)
```

### 6.2 Log Format

```
2026-06-24 14:30:00,000 | INFO    | api.main          | File logging initialized: logs\api_log_2026-06-24_14-30-00.log
2026-06-24 14:30:00,123 | INFO    | api.main          | API directories initialized
2026-06-24 14:30:05,456 | INFO    | src.extraction    | Extracting sheets from Form16...
2026-06-24 14:30:06,789 | INFO    | src.llm_reviewer  | LLM Provider: openrouter | Base URL: https://openrouter.ai/api/v1
2026-06-24 14:30:08,012 | WARNING | src.llm_reviewer  | LLM not connected: ... — using deterministic fallback
2026-06-24 14:30:08,345 | INFO    | src.discrepancies | Discrepancy: salary delta=25000 materiality=medium
```

### 6.3 What Gets Logged

All modules propagate to root logger, so the file captures:

| Module | Events |
|--------|--------|
| `api.main` | Session creation, uploads, pipeline start/complete |
| `api.services.case_processor` | Pipeline stage transitions, progress updates |
| `src.extraction` | File parsing, sheet extraction |
| `src.mapping` | Canonical model building, identity detection |
| `src.validation` | Data quality issues |
| `src.discrepancies` | Each discrepancy found with delta |
| `src.llm_reviewer` | LLM provider, model, success/fallback |
| `src.decision` | Decision type, reason codes |
| `src.document_gen` | Template rendering, PDF conversion |
| `src.output` | Output file writes |

### 6.4 Log Rotation

A new file is created each time the API starts. Filename includes timestamp:
```
logs/api_log_2026-06-24_14-30-00.log
logs/api_log_2026-06-25_09-15-22.log
```

---

## 7. Data Flow

```
User uploads:  Form_16.xlsx, AIS.xlsx, ITR_Extract.xlsx
    │
    ▼
/api/session/{id}/upload  (3 calls, one per file)
    │
    ▼
Files saved to: api/input/{session_id}/
  form16.xlsx, ais.xlsx, itr.xlsx
    │
    ▼
POST /api/session/{id}/process
    │
    ▼
Pipeline starts in background thread:
  ┌─────────────────────────────────────────────────┐
  │ 1. Extraction:                                  │
  │    extract_with_docling(Form16)                 │
  │    extract_with_docling(AIS)                    │
  │    extract_with_docling(ITR)                    │
  │       → raw sheet-by-sheet data                 │
  ├─────────────────────────────────────────────────┤
  │ 2. Mapping:                                     │
  │    build_canonical_case()                       │
  │       → CanonicalTaxCase (Pydantic model)       │
  ├─────────────────────────────────────────────────┤
  │ 3. Validation:                                  │
  │    validate_tax_case()                          │
  │       → { is_valid, issues }                    │
  ├─────────────────────────────────────────────────┤
  │ 4. Discrepancies:                               │
  │    reconcile_case()                             │
  │       → [Discrepancy, ...]                      │
  ├─────────────────────────────────────────────────┤
  │ 5. LLM Review:                                  │
  │    run_vllm_review()                            │
  │      ├── LangChain → OpenRouter API             │
  │      └── or fallback_llm_review()               │
  │       → { case_summary, findings, ... }         │
  ├─────────────────────────────────────────────────┤
  │ 6. Decision:                                    │
  │    compose_decision()                            │
  │       → DecisionResult                          │
  ├─────────────────────────────────────────────────┤
  │ 7. Document Generation:                         │
  │    render_docx_template(report)                 │
  │    render_docx_template(notice)                 │
  │    convert_docx_to_pdf()                        │
  ├─────────────────────────────────────────────────┤
  │ 8. Output:                                      │
  │    package_case_outputs()                       │
  │       → JSON + DOCX + PDF files                 │
  └─────────────────────────────────────────────────┘
    │
    ▼
Frontend polls /api/session/{id}/progress every 2s
    │
    ▼
result_ready=true → GET /api/session/{id}/report
    │
    ▼
User views report, decides on notice
    │
    ▼
POST /api/session/{id}/notice-decision { generate_notice: true/false }
```

---

## 8. API Endpoint Reference

### Session Management

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| `GET` | `/api/health` | — | `{ status: "ok" }` | Health check |
| `POST` | `/api/session/init` | — | `{ session_id, report_template_found, notice_template_found }` | Create new session |

### File Upload

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| `POST` | `/api/session/{id}/upload` | `multipart/form-data { file }` | `{ session_id, uploaded_files, all_uploaded }` | Upload Form16/AIS/ITR file |
| `POST` | `/api/session/{id}/upload-template` | `multipart/form-data { file, template_type }` | `{ session_id, template_uploaded }` | Upload DOCX template |

### Processing

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| `GET` | `/api/session/{id}/status` | — | `{ session_id, step, uploaded_files, ... }` | Current session state |
| `POST` | `/api/session/{id}/process` | — | `{ status: "started" }` | Start pipeline in background |
| `GET` | `/api/session/{id}/progress` | — | `{ step, progress, message, logs, result_ready, error }` | Poll progress + logs |

### Results

| Method | Endpoint | Request | Response | Description |
|--------|----------|---------|----------|-------------|
| `GET` | `/api/session/{id}/report` | — | `{ case_summary, discrepancies, llm_review, ... }` | Full report data |
| `GET` | `/api/session/{id}/notice` | — | `{ case_id, assessee_name, pan, ... }` | Notice preview data |
| `POST` | `/api/session/{id}/notice-decision` | `{ generate_notice: bool }` | `{ notice_generated, notice_files }` | Confirm or skip notice |
| `GET` | `/api/files/{session_id}/{filename}` | — | File stream | Download generated file |
| `GET` | `/api/session/{id}/logs` | `?offset=0` | `{ logs, total }` | Raw log messages |

---

## 9. Error Handling & Fallbacks

### 9.1 LLM Failure Chain

```
Missing .env / API key
    ↓
create_chat_model() raises ValueError("API key not found")
    ↓
try/except in run_vllm_review() catches it
    ↓
fallback_llm_review() produces deterministic output
    ↓
review["_fallback_reason_detail"] = "LLM connection failed"
    ↓
decision.py: llm_valid = False
    ↓
Frontend shows yellow banner: "LLM Review Unavailable — Deterministic Fallback Used"
```

### 9.2 Decision Override Logic

```
LLM says "notice" but no rule-based discrepancy meets ₹50K/₹1L threshold
    ↓
decision.py: notice_required = False
    ↓
reason_codes: ["LLM_NOTICE_OVERRIDDEN_NO_THRESHOLD"]
```

### 9.3 File Generation Fallbacks

- **No notice template** → `Notice_Fallback.json` written instead
- **No report template** → Report skipped, JSON fallback
- **DOCX render fails** → Fallback JSON written with context
- **PDF conversion fails** → Error logged, DOCX provided as fallback

### 9.4 Frontend Error Handling

- `ErrorBoundary.tsx` — catches React render crashes, shows reload button
- `useCaseProcessing.ts` — polling errors caught silently, API errors displayed
- `ProcessingScreen.tsx` — detects `progress.error` and calls `onError()`
- `ReportViewer.tsx` — shows yellow banner when LLM fallback active
- All API calls have try/catch with user-friendly error messages

---

## File Index

| Path | Lines | Purpose |
|------|-------|---------|
| `frontend/src/App.tsx` | 135 | Step router, state wiring |
| `frontend/src/services/api.ts` | 87 | Axios HTTP client |
| `frontend/src/hooks/useCaseProcessing.ts` | 255 | State + polling logic |
| `frontend/src/types/index.ts` | 92 | TypeScript interfaces |
| `frontend/src/components/FileUpload.tsx` | 230 | Upload UI |
| `frontend/src/components/ProcessingScreen.tsx` | 151 | Progress display |
| `frontend/src/components/ReportViewer.tsx` | 378 | Report display |
| `frontend/src/components/NoticeReview.tsx` | 173 | Notice decision |
| `frontend/src/components/NoticeViewer.tsx` | 322 | Notice preview/download |
| `frontend/src/components/ErrorBoundary.tsx` | 45 | Error fallback |
| `frontend/vite.config.ts` | 15 | Vite proxy config |
| `api/main.py` | 385 | FastAPI endpoints |
| `api/models.py` | 94 | Pydantic models |
| `api/services/case_processor.py` | 314 | Pipeline orchestration |
| `src/config.py` | 178 | LLM config, env loading |
| `src/llm_reviewer.py` | 450 | LLM call + fallback |
| `src/prompts.py` | 79 | System prompts |
| `src/extraction.py` | 189 | XLSX/DOCX parsing |
| `src/mapping.py` | 455 | Canonical model builder |
| `src/validation.py` | 45 | Data quality checks |
| `src/discrepancies.py` | 155 | Rule-based engine |
| `src/decision.py` | 92 | Decision composition |
| `src/document_gen.py` | 537 | DOCX/PDF generation |
| `src/output.py` | 90 | JSON output |
