# Phase 9 — Local assessment security and reliable job failures

## What changed

- Optional **single-user** `CARE_GUIDE_API_KEY` authentication protects all `/api/*` endpoints except health. Frontend lets you enter the key, stored only in that browser tab (sessionStorage). **An empty key disables protection.** This is a local demonstration safeguard, **not** secure multi-user authentication, per-tenant authorization, TLS, rate limiting, or production readiness.
- Basic container/file signature checks reject invalid PDFs, images, XLS/XLSX and binary CSV uploads. Existing upload size limits remain. This does **not** replace file antivirus scanning, decompression-bomb controls, sandboxing or malicious macro defenses.
- Unexpected task exceptions in parsing, invoice validation, database/index writing now mark the document `failed` and append a processing-history event. The prior missing-supplier `.casefold()` defect is fixed.
- Worker runs as a non-root user (UID 10001). Existing named Docker volumes created as root may need a **one-time ownership change** as below.
- `GET /api/documents/{id}/history` returns the most recent 100 processing events.
- Automatic retries are not enabled: the existing **Reprocess** action manually queues failed documents. The prototype does **not** recover automatically from power loss, OS-killed workers or lost Celery tasks. Those require a watchdog and durable task leases.

## Windows upgrade preserving current volumes

1. Back up the working Phase 8 folder. Copy the contents of Phase 9 into that **same original Compose directory**. Preserve `.env`. Stop services with `docker compose down` **without** `-v`.
2. In the project directory create or edit `.env`: `CARE_GUIDE_API_KEY=` followed by a long, random secret. For example generate one in PowerShell with `[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))`. Never commit `.env` to Git.
3. **Before building the non-root service**, repair existing upload/cache volumes if needed (this one-time command runs as root on the project's existing named volumes):

   ```powershell
   docker compose run --rm --user root --entrypoint sh backend -c "mkdir -p /app/uploads /app/models && chown -R 10001:10001 /app/uploads /app/models"
   ```

   If the old backend image has not been rebuilt, run `docker compose build backend` first. This operation does not delete data, but it can take time if model cache is large.
4. Run `docker compose up --build -d`, then `docker compose ps` and `docker compose logs --tail=50 worker`.
5. Open `http://localhost:5173` and enter your key in the **Local API access key** field. Refresh the document list. Your original files should still be there.
6. Run `docker compose exec backend pytest -q` and test one CSV, one bad upload, and one reprocess. Test the history endpoint using `Invoke-RestMethod -Uri "http://localhost:8000/api/documents/<ID>/history" -Headers @{ 'X-API-Key'='<YOUR_SECRET>' }`.

## Important caveats

- On localhost, the frontend proxies requests from `/api` to the backend. The API listens on port 8000; when using it from Swagger or PowerShell you must supply the `X-API-Key` header if authentication is enabled. The unprotected `/docs` page remains visible, but requests to protected endpoints will return 401 without a key.
- With no TLS, API-key headers can be intercepted across an untrusted network. Bind ports to localhost, do not expose this app to the public internet, and use synthetic or permission-cleared documents only.
- Existing `processing` rows from an earlier crash are **not** automatically reset by this release. Reprocess only when the worker has no active work and after confirming a job is truly abandoned.
- The Phase 9 automated tests use local SQLite, mocked failure paths and small sample files. They are not security penetration tests, load tests or end-to-end production verification.
