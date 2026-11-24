# Phase 10C — End-to-End Benchmark

This benchmark uses the actual HTTP backend and Celery worker, not the offline extraction evaluator. It **creates new records** and retains them for inspection.

## Install

Back up your working folder and retain `.env`. Replace project code with the Phase 10C package, then from PowerShell in the project root:

```powershell
docker compose up -d --build

docker compose ps
```

The backend service includes a read-only `./examples:/examples:ro` mount to fix previous reconciliation test fixture failures. If you modified Compose yourself, verify that this mount appears exactly once.

## Run

```powershell
docker compose exec backend python -m pytest -q /app/tests
docker compose exec backend python -m app.benchmark_e2e --input /examples/sample_invoice.csv --runs 3 --output /app/evaluation/e2e_results
docker compose exec backend cat /app/evaluation/e2e_results/e2e_evaluation.md
```

The script uses the `CARE_GUIDE_API_KEY` environment variable already supplied to the backend through Compose. **Never paste the secret into the command or share it.** A nonzero script exit status indicates one or more runs did not reach `completed` with a retrievable structured result; a report is saved even on such failure.

Copy reports to Windows:

```powershell
New-Item -ItemType Directory -Force -Path .\e2e-evaluation-output
docker compose cp backend:/app/evaluation/e2e_results/e2e_evaluation.md ./e2e-evaluation-output/e2e_evaluation.md
docker compose cp backend:/app/evaluation/e2e_results/e2e_evaluation.json ./e2e-evaluation-output/e2e_evaluation.json
```

## Metrics and limitations

- `upload_seconds`: HTTP request time for transferring/storing source document.
- `enqueue_seconds`: HTTP request time to request processing.
- `queue_to_terminal_seconds`: elapsed time from accepted process request to observed terminal status, **including polling delay**.
- `total_seconds`: full measured client operation (upload, enqueue, polling, result and history fetch).
- `completed_with_result`: finished with a retrievable structured document result; **not** field-extraction accuracy.
- Only sequential performance is tested. This does not prove performance under concurrent loads.
- The first run may involve initial embedding model loading/downloads. If it is much slower, preserve all results and report this separately.
- Don't run this against a production server or with sensitive documents.
- If the benchmark times out, check `docker compose logs --tail=100 worker` and document status/history. The script does not kill a running Celery task.

## Known gaps

True queue lag versus worker execution time requires timestamped start/end task telemetry; this version measures their aggregate. Reliability under worker crashes, multiple concurrent users, large scanned PDFs and mixed document types remains for further tests.
