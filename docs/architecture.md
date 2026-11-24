# Phase 2 architecture

```mermaid
flowchart TD
  Browser[React + Vite web interface] -->|Upload / process / results| FastAPI[FastAPI REST API]
  FastAPI -->|Metadata and status| PG[(PostgreSQL)]
  FastAPI -->|Store file| Files[(Shared uploaded_files volume)]
  FastAPI -->|Queue document ID| Redis[(Redis broker)]
  Redis -->|Consume job| Worker[Celery worker]
  Worker -->|Load original file| Files
  Worker --> Extractor[PyMuPDF / Tesseract / openpyxl / xlrd / csv]
  Extractor -->|Preview JSON and result status| PG
  Browser -->|Poll status every 5s| FastAPI
```

`documents` (existing Phase 1): id, original_filename, stored_filename, content_type, size_bytes, sha256, status, error_message, created_at.

`document_results` (new Phase 2): document_id (foreign key to documents.id, primary key), result_json (JSON).

Changes are additive: Phase 2 creates a separate results table and preserves Phase 1 document rows.

There is no automatic job retry, user accounts, semantic search or invoice extraction yet. Worker failures update the document to `failed`; job reprocessing is manual.
