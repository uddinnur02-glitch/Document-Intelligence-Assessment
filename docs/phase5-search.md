# Phase 5 — Search and expanded spreadsheet text

## Implemented
- CSV/XLSX/XLS: iterates across all rows of each sheet within MAX_ROWS=25000 and MAX_SHEETS=50. Keeps 20-row UI previews, and also accumulates bounded full row text up to MAX_EXTRACTED_CHARS=250000 for extraction, invoice parsing, and keyword search.
- New document_chunks table (created automatically on startup) stores searchable 1,800-character blocks of the extracted text. Reprocessing replaces the chunks.
- GET /api/search?q=term&limit=20 implements case-insensitive literal substring matching on filenames and stored extracted text.
- React search panel with results and snippets.
- Earlier processed files must be reprocessed once to populate DocumentChunk.

## Limitations (important for assessment)
- Search is not semantic and not yet PostgreSQL full-text/GiN indexed; SQL ILIKE is suitable for a small demo only.
- Extraction is **not exhaustive** if the 250,000-character cap is reached. The `truncated` field reports this. Cells are clipped to 350 characters and 60 columns per row.
- PDF extraction continues to store only 4,000 characters per page and max 250,000 joined characters. 1,000-page scanning needs throughput tests before any performance claim.
- Line-item reconciliation remains header-based and **20-row preview limited**, even though additional spreadsheet text is now retained. There is no guarantee of accurate reconciliation for arbitrary large documents.
- No user authentication, file scanning, audit logging, rate limiting, semantic vectors, or production data retention policy yet. Do not expose the development server on a public network.

## Windows upgrade
1. Back up Phase 4 directory. `docker compose down` (never add `-v`).
2. Overlay Phase 5 project source over the original working folder and keep `.env`.
3. `docker compose up --build -d`
4. `docker compose exec backend pytest -q`
5. Reprocess an existing CSV/XLSX document; then search for its contents from the frontend.
