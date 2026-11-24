# Care Guide submission readiness checklist

## Repository and security

- [ ] Run `git status --short` and inspect every staged file before publishing.
- [ ] Confirm `.env` and other secrets are not tracked (`git ls-files .env`). Rotate any shared/weak keys.
- [ ] Do not upload private customer documents, production invoices or secret-bearing logs.
- [ ] Confirm tracked sample files are synthetic or consented.
- [ ] Consider replacing dev-only Compose hard-coded PostgreSQL password before deployment; the current configuration is for local demonstration only.
- [ ] Validate actual output of `docker compose exec backend python -m pytest -q /app/tests`.
- [ ] Verify build from a clean clone without destroying your current data.

## Deliverables

- [ ] GitHub repository URL with README and setup steps.
- [ ] Source code for backend, frontend, workers and extraction flows.
- [ ] Architecture diagram and schema (`docs/system-architecture.md`).
- [ ] Evaluation report with exact sample sizes, timing scope, error handling and limitations (`docs/final-evaluation-report.md`).
- [ ] Verified raw benchmark JSON/MD artifacts from your local environment, placed in `submission-evidence/` after reviewing privacy.
- [ ] Updated regression test output (save `pytest` console text with timestamp/system info).
- [ ] Recorded walkthrough video URL.
- [ ] AI assistance disclosure and prompts as requested by the employer.
- [ ] Application email, updated CV, portfolio and two professional references if separately requested by employer; avoid fabricating contact details.

## Windows commands

```powershell
# Existing project — retain volumes
docker compose up --build -d
docker compose ps
docker compose exec backend python -m pytest -q /app/tests

# Save test evidence locally, including failures if any
docker compose exec backend python -m pytest -q /app/tests 2>&1 | Tee-Object -FilePath .\regression-tests.txt

# Copy locally measured results out of container
New-Item -ItemType Directory -Force -Path .\submission-evidence
docker compose cp backend:/app/evaluation/ocr_results/ocr_evaluation.md .\submission-evidence/ocr_evaluation.md
docker compose cp backend:/app/evaluation/ocr_results/ocr_evaluation.json .\submission-evidence/ocr_evaluation.json
docker compose cp backend:/app/evaluation/e2e_results/e2e_evaluation.md .\submission-evidence/e2e_evaluation.md
docker compose cp backend:/app/evaluation/e2e_results/e2e_evaluation.json .\submission-evidence/e2e_evaluation.json
```

For Phase 10A, copy the local `evaluation.md` and `evaluation.json` benchmark results from the path you actually used (for example `/app/evaluation/benchmark_results/`). Avoid confusing them with the older four-case evaluation files in `/app/evaluation/results`.

## GitHub upload (after review)

```powershell
git init
git add .
git status --short
git commit -m "Document intelligence assessment prototype and evaluation"
# Create a GitHub repository in your own account, then follow its URL-specific remote instructions.
```

Publish only after reviewing tracked files. The repository URL and video link cannot be invented or created without your account action.
