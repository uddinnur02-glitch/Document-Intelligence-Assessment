# Phase 6 — Semantic search and native PDF table detection

## New behavior

- The original `GET /api/search?q=...` **keyword** endpoint remains unchanged.
- New `GET /api/search/semantic?q=...&limit=10` ranks previously indexed document chunks by dense-vector cosine similarity using the local FastEmbed ONNX model `BAAI/bge-small-en-v1.5`.
- The worker adds embeddings to a **new nullable `document_chunks.embedding` JSON column**, and the API startup runs an additive upgrade for old PostgreSQL/SQLite installations. Previous chunks will have no embeddings until their documents are reprocessed.
- Local-only inference: document text is **not sent to a hosted model API**, though the embedding model **is downloaded from an external repository on first use** and then cached in the Docker `model_cache` volume. In offline environments, provide the model files ahead of time.
- PyMuPDF `find_tables()` locates detectable **digital/vector PDF tables**. Detected table rows and page/table provenance appear in `result.pdf_tables` and feed the Phase 4 line-item parser. Complex layouts and scanned tables may not be detected; OCR still provides page text.

## Safe upgrade from Phase 5 (Windows, VS Code)

1. Make a copy of your Phase 5 project folder and back up valuable data. Preserve your original `.env` file.
2. In the **original** project folder, run `docker compose down` **without `-v`**.
3. Extract the Phase 6 ZIP and copy all extracted project files into your **original** project folder, replacing files of the same name. Do not copy over your `.env`.
4. Run `docker compose up --build -d`, then `docker compose ps`. First rebuild may take longer due to the ONNX inference dependency; the model is fetched on first document processing or embedding search, not during container build.
5. Run `docker compose exec backend pytest -q` and inspect `docker compose logs --tail=100 worker` if indexing is slow.
6. Reprocess one previously uploaded document using the frontend's **Reprocess** button; semantic vectors are not retroactive. In the search panel choose **Semantic** and search a concept, for example `payment for medical supplies`. Use a document containing relevant content. Results are ranked by **similarity**, not a guarantee of correctness.
7. Upload a PDF with a digitally selectable line-item table, process it, and click **View result → Detected PDF tables**. Check the `line_items` section and manually verify against the PDF. Scanned or unbordered invoices may not produce tables.

## API usage

`GET http://localhost:8000/api/search/semantic?q=medical%20supply%20invoice`

Example shape: `{"query":"...", "results":[{"document_id":"...", "filename":"...", "status":"completed", "snippet":"...", "score":0.7, "chunk_index":0}], "count":1, "note":"..."}`.

If no vectors are indexed, the endpoint returns an empty list and a helpful note. A failed model load produces HTTP 503 when embeddings are present; the worker records `semantic_warning` and still stores extracted text. If semantic indexing is not needed or your machine lacks memory, set `SEMANTIC_ENABLED: "false"` in the Compose backend environment; keyword search will continue to work. **Do not** disable it while expecting new semantic results.

## Limits and security

- Prototype similarity calculation scans up to 2,000 indexed chunks in Python and stores floating-point arrays in JSON. It is **not pgvector/HNSW** or a scalable 1,000-page semantic retrieval benchmark.
- The stored text retains previous character/page limits, and line-item extraction is conservative; results may be incomplete.
- There is **no user authentication or tenant separation**. Only process synthetic or non-sensitive demonstration files. Do not expose port 8000 publicly.
- The first local model download needs internet access and disk space. The embedding package can increase Docker build time and image size.
- The prototype has no Alembic migrations yet; the additive schema upgrade addresses Phase 5 compatibility but is not a general database migration framework.

## Testing

`docker compose exec backend pytest -q` includes tests for API embedding retrieval (with a deterministic mocked encoder), cosine scoring, and vector-PDF native table parsing. These checks do **not** establish real-world extraction accuracy, AI retrieval quality, or Docker throughput. Collect actual measured metrics using representative labeled invoices before Care Guide submission.
