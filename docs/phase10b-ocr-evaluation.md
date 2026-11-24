# Phase 10B — OCR & invoice field evaluation

This release adds an **offline** evaluation harness; it does not change document processing endpoints, worker queues, or authentication.

## Run on Windows PowerShell / Docker

Start from your ORIGINAL Phase 9 Compose directory (retain your `.env` and volumes):

```powershell
docker compose down
# Back up existing source, then replace project source files with this Phase 10B package.
docker compose up --build -d
docker compose ps
```

The fixture generator makes entirely artificial invoices (PNG, JPG, TIFF and a two-page **image-only** PDF). Run:

```powershell
docker compose exec backend python -m app.generate_ocr_fixtures --output /app/evaluation/ocr_fixtures
docker compose exec backend python -m app.evaluate_ocr --manifest /app/evaluation/ocr_fixtures/manifest.json --output /app/evaluation/ocr_results
docker compose exec backend cat /app/evaluation/ocr_results/ocr_evaluation.md
```

Copy reports to Windows:

```powershell
New-Item -ItemType Directory -Force -Path .\ocr-evaluation-output
docker compose cp backend:/app/evaluation/ocr_results/ocr_evaluation.md ./ocr-evaluation-output/ocr_evaluation.md
docker compose cp backend:/app/evaluation/ocr_results/ocr_evaluation.json ./ocr-evaluation-output/ocr_evaluation.json
```

## Notes

- **CER**: character edit distance divided by the ground-truth character count. **WER**: word edit distance divided by ground-truth word count. Scores can exceed 1 when insertions dominate.
- All OCR and invoice field metrics are measured from the local extractor and rule-based invoice parser, not the LLM or browser.
- `expected_fields` in the manifest represent manually verified labels, not predictions. Missing expected fields aren't scored. Explicit `null` is a label for absent fields.
- The two-page PDF has two visually distinct invoices. Text accuracy is evaluated over both pages, but invoice-field labels target only the first invoice (the current parser is document-level, not per-invoice).
- **Do not publish sensitive real business invoices.** For a credible submission, add consented/anonymized scanned invoices and verify their ground-truth texts and fields separately.
- This is a smoke/regression dataset, not proof of production-scale OCR performance or a statistically representative real-world accuracy estimate.
- Avoid uploading invoices that include personal or banking details to public GitHub.
- If the existing backend Dockerfile does not include `COPY tests ./tests`, add it before running tests within the container. Keep this only for development and evaluation.

## Tests

```powershell
docker compose exec backend python -m pytest -q /app/tests
```

## Remaining assessment gaps

Full API → Redis/Celery → PostgreSQL processing latency; real-world OCR dataset; 1,000-page scanned PDF reliability; per-document multi-invoice extraction; privacy and security hardening for deployment.
