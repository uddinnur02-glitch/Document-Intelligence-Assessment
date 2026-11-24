# Final evaluation report — measured evidence

**Measurement date: 24 November 2026.** Values below were supplied from the user's local Windows/Docker environment. This report combines the distinct benchmark scopes without conflating them. Raw results should be committed alongside the report after reviewing for sensitive information.

## Summary

| Evaluation | Sample | Main result | Scope |
|---|---:|---|---|
| Phase 10A: large digital PDF | 1 synthetic 1,000-page PDF | Completed in **6.258415 s**; no truncation flag | Offline synchronous extraction + local parsing only |
| Phase 10B: OCR and invoice fields | 5 synthetic cases (4 valid, 1 deliberately corrupt) | **4/4** valid processed; corrupted sample rejected; normalized micro CER **0.0** and WER **0.0**; **32/32** labeled invoice fields exact-match | Offline OCR + rule-based invoice extraction only |
| Phase 10C: end-to-end API | 3 sequential copies of sample CSV | **3/3** completed with results; mean **1.3822 s**, median **0.636 s**, max **2.93 s** | Local HTTP → API → Redis/Celery → PostgreSQL → results/history |

## Phase 10A detail

- Processed cases: **1/1**; processing success rate **1.0**; failures **0**.
- Reported processing time: mean/median/max **6.258415 seconds**.
- `truncated_successful_cases = 0` for this synthetic run.
- **Not assessed:** page-by-page ground-truth content coverage, scanned 1,000-page OCR accuracy, API upload and database time, user concurrency.

## Phase 10B detail

| Case | Outcome | Elapsed seconds | CER | WER |
|---|---|---:|---:|---:|
| clear_png | Processed | 0.881646 | 0 | 0 |
| degraded_jpeg | Processed | 0.396854 | 0 | 0 |
| tiff_image | Processed | 0.956055 | 0 | 0 |
| scanned_pdf (2 pages) | Processed | 1.499818 | 0 | 0 |
| corrupted_png | Rejected as expected | 0.092044 | N/A | N/A |

Reported mean elapsed time **0.765283 seconds**, across the five cases. Reported invoice-field exact match **1.0** over **32** labels; no page-count mismatches or flagged truncations on successful cases. The 2-page scan uses the first invoice for invoice-field ground truth while text scoring includes both pages. These controlled synthetic examples are **not** a real-world OCR validation set.

## Phase 10C detail

| Run | Status | Upload (s) | Enqueue (s) | Queue-to-terminal (s) | Total (s) | Result |
|---|---|---:|---:|---:|---:|---|
| 1 | completed | 0.0425 | 0.3180 | 2.5470 | 2.9300 | retrieved |
| 2 | completed | 0.0506 | 0.0563 | 0.5138 | 0.6360 | retrieved |
| 3 | completed | 0.0311 | 0.0205 | 0.5147 | 0.5807 | retrieved |

All runs recorded `queued`, `processing`, and `completed` audit events; **0** failures, request errors or timeouts. Note that polling contributes to queue-to-terminal duration and initial startup may contribute to Run 1 latency. Three sequential runs do not measure concurrency or sustained throughput.

## Evidence interpretation and outstanding validation

- A 100% outcome in **1**, **4**, or **3** positive cases cannot be generalized to production reliability or real-world accuracy.
- OCR error rates and field accuracy are distinct metrics; the end-to-end test does not establish field correctness.
- No independent benchmark of scanned PDF table reconstruction, real 1,000-page OCR workloads, simultaneous uploads, adversarial input, or high-load recovery has been provided.
- The earlier `50 passed, 4 failed` test output showed missing `/examples` fixture paths in the container, not failed invoice predictions. A Compose mount was added in the Phase 10C package, but **the final complete regression pass count remains unconfirmed here**; run it and record actual results before submission.
- A successful processing state can still contain capped output; verify page counts, truncation flags and representative source text when making completeness claims.

## Suggested final report statement

> In a local synthetic evaluation, the prototype completed a 1,000-page digital-text PDF extraction in 6.258 seconds without reported truncation; achieved 0 normalized OCR character/word error and 32/32 exact invoice-field matches on a small controlled OCR dataset; and completed three sequential full-stack CSV jobs with a mean upload-to-result time of 1.382 seconds. These are development measurements and should not be interpreted as real-world accuracy, OCR robustness, or concurrent performance guarantees.
