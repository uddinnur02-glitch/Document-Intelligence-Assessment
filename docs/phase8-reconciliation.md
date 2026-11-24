# Phase 8 — Streaming spreadsheet line items and coverage-aware reconciliation

## What changed

- The PDF/CSV/Excel upload, OCR, API and Celery background workflow from Phases 1–7 are preserved.
- Spreadsheet line items now parse **all rows scanned by the existing extractor**, not just the first 20 preview rows. The preview remains 20 rows to keep the UI compact.
- Each parsed line item retains its sheet name and row number as evidence.
- Multi-sheet workbooks are supported; the parser requires explicit `Description`, `Qty`, `Unit Price`, `Amount` headers (with supported aliases) on each table.
- The comparison now treats a changed unit price for the same description as a **mismatch**, not two unmatched products.
- The API returns extraction coverage metadata and flags incomplete sources. The UI displays this metadata and only renders the first 100 rows to remain responsive.
- Reprocessing older files is necessary: old stored results have only preview-limited data and lack the new coverage metadata.

## Test locally (Windows + Docker Desktop)

From your **original** Phase 7 Compose project directory:

```powershell
# Take a backup before replacing source code.
docker compose down
# Copy contents of Phase 8 zip's careguide-document-intelligence into existing folder.
# Do not overwrite your .env file or delete Docker volumes.
docker compose up --build -d
docker compose ps
docker compose exec backend pytest -q
```

Expected in this version: **43 passing backend tests** (where installed dependencies match the declared requirements).

Open `http://localhost:5173` and upload both files in `examples/phase8_long_invoice.csv` and `examples/phase8_long_invoice_mismatch.csv`. Process each, open one, and compare it with the other. The change on line 28 should appear as a line-item mismatch despite the UI preview containing only 20 rows. Inspect **Extraction coverage and limits** as well.

## API verification

`GET /api/documents/{document_id}/invoice` returns `invoice.source_coverage`, `invoice.line_items` and `invoice.warnings`.

`GET /api/compare?left_id=...&right_id=...` returns line item comparisons, summary, source coverage and limitations. Expected statuses:

- `review_required`: extracted fields or line items differ, or fields are missing.
- `incomplete`: source coverage is unknown/truncated/limited, or an invoice has no line items.
- `matched_extracted_data`: no discrepancy was detected **in the extracted data**. This never guarantees source authenticity or that OCR is comprehensive.

## Scope and remaining limitations

This is an improvement in **structured spreadsheet reconciliation**, not a guarantee of full arbitrary PDF ↔ Excel verification. In particular:

- Spreadsheet parsing is limited by `MAX_SPREADSHEET_ROWS` (default 25,000 per sheet) and `MAX_SHEETS` (default 50); exceeding these limits fails explicitly.
- Parsed items are bounded by `MAX_LINE_ITEMS` (default 5,000 per sheet; combined comparisons also capped at 5,000) and warnings are emitted on limits. Very large outputs can still be expensive to store.
- Excel formulas are never executed; cached formula values may be missing.
- PDF native table extraction remains heuristic and bounded (30 tables per page and 500 rows per table). Scanned tables may not yield structured items.
- Extraction text is capped at 250,000 characters and page text previews at 4,000 characters. Truncation is marked, and incomplete comparisons cannot be called a match.
- Header-only sheets, missing headers, malformed rows and repeated product names require reviewer judgment. Matching on canonical description and occurrence order is intentionally conservative.
- The application currently has no authentication, authorization, audit trail or safe multitenancy. **Use synthetic/non-sensitive documents only** until the security phase.
- No performance claims are made for arbitrary 1,000-page scanned PDFs or production scale. Phase 7 synthetic timings are not real-world benchmarks.
