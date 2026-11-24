# Care Guide — AI-Powered Document Intelligence System

**Assessment prototype · React/Vite + FastAPI + PostgreSQL + Redis/Celery**

The application accepts PDF, JPEG, PNG, TIFF, XLSX, XLS and CSV files; extracts text or spreadsheet previews; performs rule-based invoice parsing and validations; compares invoices and line items; and provides keyword and optional semantic search. Scanned images use Tesseract OCR. A local, optional single-user API key protects API routes. This is a **demonstration**, not a production-ready financial-data service.

## Requirements

Docker Desktop (WSL2 on Windows), Docker Compose, and a browser. First use may require downloading the local embedding model if semantic indexing is enabled. **Use only synthetic or authorized documents.**

## Quick start (Windows PowerShell)

1. Extract this repository and open the folder containing `compose.yaml` in VS Code.
2. Copy `.env.example` to `.env`, then set a strong `CARE_GUIDE_API_KEY`. Keep `.env` private. The key protects the app's API; it is **not** an OpenAI/LLM API key.
3. Run:

   ```powershell
   docker compose up --build -d
   docker compose ps
   ```

4. Open the frontend at `http://localhost:5173` and API docs at `http://localhost:8000/docs`. Enter your API key in the frontend's local API access key field.
5. Upload `examples/sample_invoice.csv`, select **Process**, inspect its status/result/invoice, and optionally compare two processed documents.
6. To stop without deleting stored database/uploads: `docker compose down` (**not** `down -v`).

### Tests

```powershell
docker compose exec backend python -m pytest -q /app/tests
```

`examples/` is mounted at `/examples` inside the backend container for reconciliation tests. Do not claim a passing regression count until it has been run in your own environment.

### Evaluation commands

```powershell
# 1,000-page synthetic digital-text PDF offline benchmark
# (generates fixture first; inspect the manifest path before running)
docker compose exec backend python -m app.generate_benchmark --pages 1000 --output /app/evaluation/docs/synthetic_1000_pages.pdf

# OCR and invoice-field synthetic evaluation
docker compose exec backend python -m app.generate_ocr_fixtures --output /app/evaluation/ocr_fixtures
docker compose exec backend python -m app.evaluate_ocr --manifest /app/evaluation/ocr_fixtures/manifest.json --output /app/evaluation/ocr_results

# HTTP → FastAPI → Redis/Celery → PostgreSQL end-to-end benchmark
docker compose exec backend python -m app.benchmark_e2e --input /examples/sample_invoice.csv --runs 3 --output /app/evaluation/e2e_results
```

See **[combined evaluation report](docs/final-evaluation-report.md)** for the user's measurements, sample sizes and limitations; **[architecture and schema](docs/system-architecture.md)**; **[API and demo guide](docs/walkthrough-and-api.md)**; **[submission checklist](docs/submission-checklist.md)**; and **[AI assistance disclosure template](docs/ai-assistance-disclosure.md)**.

## Implemented operations

- Upload and list documents; queue, retry manually and inspect background processing; view structured results, errors and history.
- OCR of scanned PDFs and images; spreadsheet processing across sheets; digital PDF table recognition where available.
- Rule-based invoice-field extraction, arithmetic and missing-field checks; human corrections; duplicate checks.
- Line-item and cross-document comparisons; keyword and optional local semantic search.
- Automated offline evaluation and real-API sequential benchmarks.

## Main API endpoints

| Method | Endpoint | Action |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/documents` | Upload a document (`file` multipart field) |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{id}` | Document status |
| POST | `/api/documents/{id}/process` | Queue / reprocess |
| GET | `/api/documents/{id}/result` | Extracted processing result |
| GET | `/api/documents/{id}/invoice` | Invoice and validation results |
| PUT | `/api/documents/{id}/invoice` | Correct invoice fields |
| GET | `/api/documents/{id}/history` | Processing audit events |
| GET | `/api/search?q=...` | Keyword search |
| GET | `/api/search/semantic?q=...` | Semantic search (optional embeddings) |
| GET | `/api/compare?left_id=...&right_id=...` | Cross-document comparison |

When configured, send the API key as `X-API-Key`. The public `/api/health` endpoint is exempt. OpenAPI docs `/docs` are reachable in the local demo; do not expose the service publicly as-is.

## Known limitations and security notes

- Single shared API key, no user accounts, per-document authorization, TLS termination, rate limiting, or production secret management.
- Compose contains **development-only database credentials**, and backend/frontend ports are exposed on the local host; **do not deploy this Compose file to a public server unchanged**.
- Upload limit defaults to 20 MB; PDFs are subject to page/text-preview caps; OCR is English-oriented; scanned-table reconstruction is limited.
- Model embedding download/first-run initialization may affect timing; benchmark records are not deleted automatically.
- `Base.metadata.create_all` and an additive SQL adjustment are used instead of versioned migrations.
- The current evaluations are synthetic and small, not external real-world accuracy or concurrency measurements.

## Repository layout

- `backend/app/` API, extraction, tasks, search, reconciliation and benchmark modules.
- `backend/tests/` automated tests.
- `frontend/src/` React interface.
- `examples/` non-sensitive synthetic examples.
- `backend/evaluation/` offline synthetic fixtures and evaluator modules.
- `docs/` architecture, evaluation, walkthrough, disclosure and submission guides.

See `docs/legacy-phase-readme.md` for the original iterative phase notes and older design decisions.
