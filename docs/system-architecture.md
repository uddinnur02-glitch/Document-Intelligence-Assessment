# System architecture and database schema

These diagrams describe the inspected Phase 10C source, not a production deployment.

## Request and processing architecture

```mermaid
flowchart LR
  Browser[React / Vite frontend] -->|HTTP upload, search, corrections, polling| API[FastAPI]
  API -->|metadata, invoice corrections, results, events| PG[(PostgreSQL)]
  API -->|original files| Files[(Shared upload volume)]
  API -->|enqueue task| Broker[(Redis)]
  Broker --> Worker[Celery worker]
  Worker -->|read documents| Files
  Worker --> Extract[PDF + image OCR + spreadsheet parsing]
  Extract --> Invoice[Rule invoice extraction / optional LLM]
  Invoice --> Validation[Validation + line-item reconciliation]
  Worker -->|extracted text, invoice JSON, embeddings, audit events| PG
  API -->|retrieve saved results| Browser
```

`SEMANTIC_ENABLED` controls embedding generation. The worker's optional LLM call is a fallback path, not a guarantee of available third-party model access.

## Database entities

```mermaid
erDiagram
  documents ||--o| document_results : has
  documents ||--o| invoice_results : has
  documents ||--o{ document_chunks : indexes
  documents ||--o{ processing_events : records
  documents {
    string id PK
    string original_filename
    string stored_filename
    string content_type
    int size_bytes
    string sha256
    string status
    string error_message
    datetime created_at
  }
  document_results {
    string document_id PK,FK
    json result_json
  }
  invoice_results {
    string document_id PK,FK
    json invoice_json
    json validation_json
    bool corrected
    datetime updated_at
  }
  document_chunks {
    int id PK
    string document_id FK
    int chunk_index
    text content
    json embedding
  }
  processing_events {
    int id PK
    string document_id FK
    string event
    text message
    datetime created_at
  }
```

The schemas are implemented in `backend/app/models.py`. SQLAlchemy creates tables at startup, with a small additive schema adjustment; Alembic migrations are not implemented.

## Processing and data considerations

Uploads are stored under a shared Docker volume. API storage and the worker must share that volume. `queued`, `processing`, `completed`, and `failed` events appear in `processing_events`. Status polling introduces latency into end-to-end timings. File format signatures are validated for supported formats, but this is not malware scanning. The same backend stores file metadata, structured results, validation issues, text/semantic index data and corrections in PostgreSQL.
