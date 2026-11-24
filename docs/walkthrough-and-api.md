# Demonstration walkthrough and API guide

## Recommended 5–7 minute recorded walkthrough

1. **00:00–00:40 Overview:** Explain the problem, supported file types and architecture. Show README and diagram.
2. **00:40–01:40 Upload + processing:** Open `http://localhost:5173`, enter the local API key privately (do not reveal it on camera), upload `examples/sample_invoice.csv`, process and show status updates.
3. **01:40–02:30 Extraction and validation:** Open the document result and invoice fields, line items, missing-field/math warnings and processing history.
4. **02:30–03:20 Corrections and comparison:** Correct an intentionally wrong field using UI, compare two sample invoices (e.g. phase4 or phase8 examples), display mismatches; do not modify private data.
5. **03:20–04:10 Search:** Demonstrate keyword and optional semantic search with processed documents. Mention model-download limitations.
6. **04:10–05:10 Evaluation:** Present the actual three benchmark reports and differentiate offline from end-to-end timings; give sample sizes.
7. **05:10–06:00 Tests and limitations:** Run pytest, show the **actual** status, briefly state security, OCR and scalability limits. End with repository structure.

Do not record the API key, database password, `.env`, private invoices or customer details. Use an incognito or clean terminal view if needed.

## Local API reference

Base URL: `http://localhost:8000`. Unless `CARE_GUIDE_API_KEY` is blank, provide `X-API-Key: <secret>` for `/api/*` routes other than `/api/health`. The following examples use a terminal environment variable (`$env:CARE_GUIDE_API_KEY`) rather than putting the secret in command history.

```powershell
# Confirm the API is up
Invoke-RestMethod http://localhost:8000/api/health

# API health is public; protected requests need a header
$headers = @{ 'X-API-Key' = $env:CARE_GUIDE_API_KEY }
Invoke-RestMethod -Uri http://localhost:8000/api/documents -Headers $headers
```

For multipart uploads, inspection and correction, the interactive API docs are available at `/docs`; ensure the API key header is added where needed. Document ID is returned on upload. Processing is a separate `POST /api/documents/{id}/process` request. Poll `GET /api/documents/{id}` until `completed` or `failed` and retrieve `/result`, `/invoice` and `/history`. Comparison takes `left_id` and `right_id` query parameters.

## Demo verification checklist

- [ ] Five Docker services are healthy/running.
- [ ] API-key request succeeds; request without key receives 401 when enabled.
- [ ] Upload/processing yields a saved result and processing events.
- [ ] Correction persists to the invoice endpoint.
- [ ] Comparison shows expected mismatch on intentionally different samples.
- [ ] Keyword search works; semantic feature is shown only if model indexing succeeds.
- [ ] Test suite completes with an actual recorded count and no fixture-path errors.
- [ ] Evaluation reports are based on local measurements and limitations are visible.
