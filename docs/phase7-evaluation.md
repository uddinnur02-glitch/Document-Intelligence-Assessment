# Phase 7 — Evidence-based evaluation and reliability

Phase 7 adds **offline, reproducible performance and extraction evaluation**, and a synthetic PDF load generator. It retains all Phase 6 API/frontend behavior. This is **not** a claim that 1,000-page scanned PDFs, arbitrary financial files, or sensitive financial deployments are production-ready.

## Windows + Docker instructions (keep current data)

1. Back up your original project folder and any important uploads. In your **existing** VS Code project folder run `docker compose down` (do not use `-v`).
2. Extract Phase 7 ZIP, copy files over the existing project's source files, preserving `.env` and the original Compose directory.
3. Run `docker compose up --build -d` then `docker compose ps`.
4. Run `docker compose exec backend pytest -q`.
5. Generate the *provided synthetic* evaluation report:

```powershell
# Run from the original project folder containing compose.yaml
# /app is the backend container's working directory
# Reports are written inside the container unless copied out

docker compose exec backend python -m app.generate_benchmark --pages 2 --output /app/evaluation/docs/synthetic_2_pages.pdf
docker compose exec backend python -m app.evaluate --manifest /app/evaluation/manifest.json --output /app/evaluation/results
mkdir evaluation-output
docker compose cp backend:/app/evaluation/results/evaluation.json ./evaluation-output/evaluation.json
docker compose cp backend:/app/evaluation/results/evaluation.md ./evaluation-output/evaluation.md
```

**Note:** Phase 7 Compose retains your existing volume/database definitions. The evaluation files are bundled with the backend image for repeatability. `evaluation-output` is a local folder you can include in your final submission.

## Optional 1,000-page digital PDF benchmark

This evaluates **one generated digital-text PDF** through the *offline* processor, not the complete web upload/Redis/Celery pipeline. Generate file and add it to a separate benchmark manifest (or replace the synthetic two-page PDF path in a copy of the supplied manifest) before running evaluator:

```powershell
docker compose exec backend python -m app.generate_benchmark --pages 1000 --output /app/evaluation/docs/synthetic_1000_pages.pdf
```

When benchmarking it, remove expected invoice fields from that case unless they match the generated page content. Run evaluation on a manifest explicitly referencing `docs/synthetic_1000_pages.pdf`. The full text will be capped by `MAX_EXTRACTED_CHARS` and by per-page previews; **check `truncated`**. Even when a 1,000-page job succeeds, the result is **not** proof of comprehensive extraction or reconciliation.

## Ground-truth datasets and reporting

- Edit `backend/evaluation/manifest.json`: each case has a relative `path`, optional `id`, optional `expect_failure`, and an `expected_fields` object containing only supported invoice keys. Use explicit `null` for a field expected to be absent. Missing labels are not scored.
- Add genuine, permission-cleared invoices and manually verify ground truth. Keep test data separate from training/tuning data. Do not put customer or financial secrets in a public repository.
- `evaluation.json` contains per-file timing, errors, field predictions/labels, and truncation indicators. `evaluation.md` gives a metric summary and per-file table.
- The provided synthetic dataset is only a smoke test. **Do not present its scores as real-world extraction accuracy.**
- Processing success rate counts all successfully returned extraction results; expected-outcome rate includes expected rejection of corrupted files.
- Timing uses `time.perf_counter` and includes file extraction and local rule-based parsing, but not upload, queue delay, database, remote LLM, embedding model loading, or frontend work.
- No semantic-search ranking evaluation is included here. That needs a relevance-labeled query set and precision@k / recall@k.
- Report your Windows hardware, CPU, RAM, Docker settings, file counts, file types, pages, model versions and configured limits alongside real metrics.

## Reliability/security limits remaining

- PDF/image OCR stores only the first 4,000 characters of each page; global text is capped at 250,000 characters by default. A processing success may therefore be incomplete.
- Invoice line-item extraction from spreadsheets is still limited to sheet previews. This is not full financial reconciliation.
- The upload service is a local assessment prototype with no user authentication or tenant access control; use synthetic data only.
- This module does not implement sustained concurrency/load tests for Redis workers or production-quality security.
