# Tax Investigation System — UI

A React + FastAPI application for automated tax compliance analysis. Upload Form 16, AIS, and ITR documents, run a forensic pipeline (rule-based + optional LLM review), and generate notices under Section 133(6).

---

## Quick Start

### Prerequisites

- Python 3.11
- Node.js 18+
- An OpenRouter API key (or any OpenAI-compatible LLM endpoint)

### Setup

```bash
# 1. Python virtual environment
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install fastapi uvicorn python-multipart

# 2. Frontend dependencies
cd frontend
npm install
cd ..

# 3. Environment configuration
copy .env.example .env
# Edit .env with your API key
```

### Run

**Option A — One-click launcher:**
```bash
runUI.bat
```

**Option B — Separate terminals:**
```bash
# Terminal 1 — API server
.venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd frontend
npx vite --host 0.0.0.0 --port 5173
```

Then open **http://localhost:5173**.

---

## User Flow

```
Upload Documents  →  Process Case  →  View Report  →  Review Notice  →  Download
   (3 files)          (pipeline)       (findings)       (decision)       (DOCX/PDF)
```

1. **Upload** 3 files: Form 16, AIS, ITR Extract (XLSX or DOCX)
2. Click **Start New Case** → upload each file into its designated slot
3. Click **Process Case** — the backend runs extraction → mapping → validation → discrepancy analysis → LLM review → decision
4. **View Report** — risk summary, discrepancy table, LLM findings, validation steps
5. **Review Notice** — if a notice is recommended, preview details then generate or skip
6. **Download** — DOCX (editable) and PDF versions of the notice

---

## LLM Configuration

Set these in `.env` (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your API key | — |
| `LLM_BASE_URL` | API endpoint | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Model name | `qwen/qwen3.5-9b` |

Supports: **OpenRouter**, **OpenAI**, **vLLM** (local), **Ollama** (local).

The system falls back to rule-based analysis if the LLM is unavailable.

---

## Project Structure

```
cohert_project/
├── api/                  # FastAPI backend
│   ├── main.py           # Endpoints (init, upload, process, report, notice)
│   ├── models.py         # Pydantic API models
│   └── services/
│       └── case_processor.py   # Pipeline orchestration
├── src/                  # Core pipeline
│   ├── config.py         # LLM config, paths, .env loading
│   ├── prompts.py        # LLM system prompts
│   ├── llm_reviewer.py   # LLM call + fallback
│   ├── extraction.py     # XLSX/DOCX extraction
│   ├── mapping.py        # Raw data → canonical models
│   ├── validation.py     # Data quality checks
│   ├── discrepancies.py  # Rule-based comparison engine
│   ├── decision.py       # Notice / report decision logic
│   ├── document_gen.py   # DOCX template rendering + PDF
│   └── output.py         # JSON output packaging
├── frontend/             # React + Vite + Tailwind
│   └── src/
│       ├── App.tsx               # Step router
│       ├── services/api.ts       # Axios HTTP client
│       ├── hooks/useCaseProcessing.ts  # State + polling
│       ├── types/index.ts        # TypeScript interfaces
│       └── components/
│           ├── FileUpload.tsx     # Drag-and-drop upload
│           ├── ProcessingScreen.tsx # Progress + logs
│           ├── ReportViewer.tsx   # Discrepancy report
│           ├── NoticeReview.tsx   # Notice decision
│           ├── NoticeViewer.tsx   # Notice download/preview
│           └── ErrorBoundary.tsx  # Error fallback
├── logs/                 # API log files (auto-created)
├── .env                  # LLM configuration (gitignored)
├── .env.example          # Configuration template
├── runUI.bat             # Windows launcher
└── requirements.txt      # Python dependencies
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| LLM fallback banner | No `.env` or bad key | Check `logs/api_log_*.log` for "API key not found" |
| API won't start | Port 8000 in use | Kill existing uvicorn process |
| Upload fails | Wrong file name | Must contain "Form16", "AIS", or "ITR" |
| Processing timeout | Large files | Check logs for prompt size issues |

### View Logs

```
logs/api_log_YYYY-MM-DD_HH-MM-SS.log
```
