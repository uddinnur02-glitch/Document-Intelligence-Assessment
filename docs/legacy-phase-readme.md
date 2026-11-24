# Phase 9 — Security and Reliable Job States

See [Phase 9 upgrade instructions](docs/phase9-security-reliability.md) before upgrading an existing installation. API authentication is **optional** and off until `CARE_GUIDE_API_KEY` is set in `.env`.

# Care Guide — Phase 7: Measured Evaluation and Reliability

See [Phase 7 evaluation guide](docs/phase7-evaluation.md). Adds offline labeled extraction metrics, per-file failure/timing reports, and a synthetic PDF page-count generator. **No real-world accuracy claims without real labeled data.** Existing Phase 6 features remain unchanged.

---

# Care Guide — AI-Powered Document Intelligence System (Phase 6)

**Current release: semantic search and native digital-PDF table extraction.** See [Phase 6 instructions](docs/phase6-semantic-pdf.md) for upgrading your existing Phase 5 project, required model download, API examples and limitations. The application remains a demonstration prototype, **not** a production-ready financial system.

**Core Phase 6 commands (in existing project folder):** `docker compose down` (never `-v`), replace source files while keeping `.env`, `docker compose up --build -d`, `docker compose exec backend pytest -q`.

**New endpoint:** `GET /api/search/semantic?q=...`. Select **Semantic** in the frontend Search documents area. Reprocess existing documents to populate local embeddings. The worker downloads a local ONNX embedding model once (cached in the named `model_cache` volume); keyword search continues to work independently.

**Native PDF table extraction:** detected tables appear in processing results under `pdf_tables`; line items are extracted only when column headers are recognizable. OCR does not reconstruct scanned tables. Data remains bounded by extraction limits.

---

## Previous-phase reference documentation

# Care Guide — AI-Powered Document Intelligence System

## Phase 2: Document processing MVP

This project extends the **Phase 1 starter**. It is an assessment prototype, not a production-ready financial-data system. Phase 2 extracts text from PDF/images and previews spreadsheet contents; **AI invoice field extraction, cross-document verification, semantic search, user authentication, and business-rule validation are not yet implemented.**

### What works

- Existing FastAPI upload, listing, and status APIs.
- New `POST /api/documents/{id}/process` endpoint, returning 202 and enqueuing a Celery job through Redis.
- New `GET /api/documents/{id}/result` endpoint for read-only results and errors.
- Digital PDF text using PyMuPDF, with Tesseract OCR fallback on low-text pages.
- JPG/PNG and multi-frame TIFF OCR via Pillow/Tesseract.
- CSV (UTF-8 BOM, UTF-16, cp1252 fallback), XLSX (openpyxl) and XLS (xlrd) parsing, including multiple sheets.
- Separate `document_results` table in PostgreSQL, created automatically at API startup, preserving the Phase 1 `documents` table.
- Frontend Process/Reprocess and View result actions; document statuses auto-refresh every five seconds.
- Error state for corrupted or encrypted documents; 1,200-page ceiling, 25k rows/sheet, 50 sheets, 20MB upload ceiling by default.

**Important limitations:** Spreadsheet results are first-20-row previews per sheet (not full financial extraction). The PDF and image response stores only 4,000 characters per page and caps the combined preview at 250,000 characters. Files are processed sequentially per worker task. This design is intended to bound output size, *not* to demonstrate 1,000-page throughput or production scalability. OCR errors are not proof of empty documents. Language pack is English only. In the current development prototype, uploaded files may contain sensitive data: use **synthetic/sample financial documents**, not private customer data. There is no authentication yet.

## Windows + Docker Desktop setup (recommended)

Prerequisites: Docker Desktop running using WSL 2, VS Code, and the ZIP extracted to a folder.

1. **Stop the Phase 1 Compose application if it is running.** In VS Code, open a terminal within the **old Phase 1 project folder**, and run:
   ```powershell
   docker compose down
   ```
   **Do not add `-v`**: that flag deletes the PostgreSQL and upload volumes. Back up data before making structural changes.
2. **Use the updated Phase 2 project files.** Unzip this Phase 2 archive and open the extracted `careguide-document-intelligence` directory in VS Code. Use the same Compose project directory name/location as before if you want to reuse the existing Compose volumes. If you unzip to a different folder, Compose may create a new project and new empty volumes; previous uploads will still exist in their original volumes but will not automatically appear in the new project.
3. Verify the VS Code terminal is in the directory containing `compose.yaml`:
   ```powershell
   dir compose.yaml
   ```
4. Start all five services (PostgreSQL, Redis, backend, worker and frontend):
   ```powershell
   docker compose up --build -d
   docker compose ps
   ```
5. Open frontend **http://localhost:5173** and Swagger API docs **http://localhost:8000/docs**.
6. Upload `examples/sample_invoice.csv` (or use your previously uploaded sample), click **Process**, observe `queued` then `processing` then `completed`, and click **View result** to see the parsed data. A very small file may skip `processing` in the UI.
7. For logs:
   ```powershell
   docker compose logs --tail=100 backend
   docker compose logs --tail=100 worker
   docker compose logs --tail=100 redis
   ```
8. To stop the application without removing volumes:
   ```powershell
   docker compose down
   ```

### If a file does not process

- `queued` for a long time: check `docker compose ps` for the `worker` and `redis` services and inspect worker logs.
- `failed`: click **View result** to read the error. Supported extensions do not guarantee valid file content.
- `503 Processing queue unavailable`: Redis or worker configuration is unavailable; check Redis logs and rerun `docker compose up -d`.
- `404` at the new endpoints: check that Docker rebuilt the backend and that you are in the updated Phase 2 project folder.
- If the frontend is old, hard-refresh the browser with `Ctrl+Shift+R` and confirm Compose rebuilt frontend.
- If old uploads are missing: the new folder likely has a different Compose project name; return to the original folder or migrate/backup volumes rather than deleting anything.

### API walkthrough

```text
GET  /api/health
POST /api/documents                 multipart form field: file
GET  /api/documents
GET  /api/documents/{id}
POST /api/documents/{id}/process    queue or reprocess (202)
GET  /api/documents/{id}/result     status, error, and extracted preview JSON
```

Result example for sample CSV (shortened):

```json
{
  "document_id": "<uuid>",
  "status": "completed",
  "error_message": null,
  "result": {
    "kind": "csv",
    "page_count": 0,
    "sheet_count": 1,
    "sheets": [{"name": "<file>.csv", "rows": 2, "preview": [["invoice","total"],["INV-001","100"]]}]
  }
}
```

Values above are an example, not results reported from your own run.

### Run tests

```powershell
# inside the running project's root
# install pytest dependencies in the backend Docker image as specified

docker compose exec backend pytest -q
```

Tests cover existing upload API behavior, unprocessed result metadata, valid PDF/CSV/XLSX/image extraction, and damaged/missing files. Tests were run in the authoring environment with available dependencies: **13 passed**. The Docker image build and Docker-based Celery processing were not run in that environment, so they require validation on your Windows installation. A measured extraction accuracy, throughput benchmark, and end-to-end performance report are still pending.

### Next planned stage (Phase 3)

- Invoice structured extraction into JSON with explicit null/uncertainty and source provenance.
- Deterministic arithmetic verification, duplicates and manual-review workflow.
- PDF-to-PDF and PDF-to-Excel comparisons by invoice ID, supplier and amounts.
- Gold-labeled dataset, measured accuracy, and repeatable performance metrics.

### Security notes

This is a local assessment prototype with default development-only credentials in `compose.yaml`, no authentication and no external exposure controls. Do not publish the configured ports to the internet or use real confidential financial documents. Production would require authentication, file scanning, resource isolation, rate limits, migration tooling, hardened secrets, and rigorous large-document stress tests.

---

## Phase 3 — Invoice extraction, validation, correction and comparison

Phase 3 adds invoice field extraction to the existing processing worker. **The default mode is conservative local regex rules, not an LLM**. When a PDF/image/CSV/XLS/XLSX is processed, the worker saves extracted text (Phase 2), invoice fields, validation findings, and whether a review is needed. Missing or ambiguous values are `null`. Default rule extraction does **not** extract line items; they remain an empty list unless opt-in LLM extraction is enabled.

### Update an existing Phase 2 installation (Windows PowerShell)

1. Back up your existing project folder, and **keep the original folder path** so Compose reuses your named volumes. Stop the app: `docker compose down` (never use `-v` when you want to keep the database).
2. Copy the Phase 3 ZIP's project contents into that same folder, replacing source files. Do not delete local `.env` files or manually stored materials.
3. Restart with `docker compose up --build -d`.
4. Check `docker compose ps`, then `docker compose logs --tail=80 backend worker`.
5. Open `http://localhost:5173`; **Reprocess** previously completed files to populate the new invoice records. Open **View result**, inspect fields, and save manual corrections.
6. Open Swagger at `http://localhost:8000/docs` to inspect new endpoints. Run `docker compose exec backend pytest -q`.

The SQLAlchemy startup creates the **new** `invoice_results` table on an existing Phase 2 database; it does not drop Phase 1/2 tables. For a real production migration system, use Alembic instead of `create_all`.

### New endpoints

- `GET /api/documents/{document_id}/invoice`: normalized invoice fields, validation findings and review/correction flag.
- `PUT /api/documents/{document_id}/invoice`: edit any of the eight supported invoice fields. Example JSON: `{"total":"1375.00"}`. Corrections do not change source document bytes.
- `GET /api/compare?left_id=<id>&right_id=<id>`: field-by-field comparison between two processed invoices, including PDFs and spreadsheets. `missing` differs from `mismatch`.

Existing upload, processing, status and raw result endpoints are unchanged. Duplicate detection checks matching supplier name and invoice number among already extracted invoice records, case-insensitively, at processing time; it does not replace a rigorous audit and is not automatically recalculated for earlier rows after edits. The numerical checks use Python `Decimal`, with tolerance of one cent. Incomplete, truncated, or ambiguous documents should be manually reviewed.

### Optional external LLM extraction — explicit opt-in

**Do not enable this on confidential employer/customer invoices without authorization.** The remote provider receives up to 45,000 characters of extracted document text. Default operation remains local and does not send document contents to a remote LLM.

In `compose.yaml`, set these in the shared `backend_env` section (both backend and worker inherit it):

```yaml
      ENABLE_LLM_EXTRACTION: "true"
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: gpt-4o-mini
```

In an untracked `.env` file next to `compose.yaml`:

```ini
OPENAI_API_KEY=your_key_here
```

Rebuild or restart the worker, then **Reprocess** the file. If no key is configured or the external call fails, the worker falls back to local extraction and includes a warning. The prompts explicitly instruct the LLM not to invent missing fields, but **LLM outputs still require human verification**. Cost and availability depend on your chosen account/model. Key-based remote extraction is optional; tests never call an external provider.

### Scope and limitations

- The Phase 2 extraction stores the first 4,000 characters per PDF page and previews only the first 20 spreadsheet rows per sheet. Thus Phase 3 does **not** guarantee complete extraction from thousand-page documents or large spreadsheets.
- Cross-document comparison matches currently available **invoice fields**, not every line item or every PDF–Excel cell. Comprehensive reconciliation is a later enhancement.
- The prototype lacks authentication, fine-grained access control, malware scanning, encrypted file storage, robust retention policy, and production-ready job retries. Do not expose it to the public internet or upload confidential customer data.
- `CREATE TABLE IF NOT EXISTS`-style startup schema is adequate for a local demo, not production migration management.
- Evaluation metrics must be measured against a labeled invoice dataset; no accuracy or throughput claim has been made.


## Phase 4 — Line items and reconciliation

Adds conservative header-based line-item parsing from spreadsheet previews and delimited PDF tables, arithmetic checks, and compare output with line-item differences. See `docs/phase4-reconciliation.md` for limitations and steps. This upgrade is compatible with the existing database: no new tables or migration required. **Back up your current folder and do not use `docker compose down -v`**.

```powershell
docker compose down
# Merge Phase 4 source into the original project directory, keeping .env
docker compose up --build -d
docker compose exec backend pytest -q
```

Both sample CSVs are under `examples/phase4_invoice_lineitems*.csv`. Upload them, process, inspect line items, and compare. For PDF tables this prototype requires `|` or TAB delimiters. Most native invoice PDFs do not use those delimiters, so no line-item result is safer than guessing.


## Phase 5 — keyword search and expanded spreadsheet text
See [docs/phase5-search.md](docs/phase5-search.md). Search endpoint: `GET /api/search?q=keyword`. Reprocess previously uploaded files to index their text. Search is literal keyword matching, **not** semantic search. The spreadsheet parser scans all bounded rows but stores up to 250,000 characters, and reconciliation may still rely on 20-row previews.

## Phase 8 — Full scanned-row spreadsheet reconciliation

See [docs/phase8-reconciliation.md](docs/phase8-reconciliation.md) for upgrade instructions, new coverage metadata, a 28-item comparison demo and current limits. Phase 8 scans all supported spreadsheet rows up to configured bounds instead of relying on the first 20 preview rows for line-item comparison. It does **not** make PDF/Excel matching universally exhaustive, nor does it make the service safe for confidential data.

## Phase 10B: OCR evaluation

See [OCR evaluation guide](docs/phase10b-ocr-evaluation.md). This adds offline OCR CER/WER and invoice-field accuracy benchmarks; it does not claim real-world performance.


## Phase 10C — End-to-end benchmark

See [Phase 10C instructions](docs/phase10c-end-to-end-benchmark.md). Run `docker compose exec backend python -m app.benchmark_e2e --input /examples/sample_invoice.csv --runs 3` to measure real HTTP upload, Celery and database results. Benchmarks create new document records.
