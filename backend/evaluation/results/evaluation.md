# Document Intelligence — Measured Evaluation

Generated (UTC): 2026-11-24T06:57:06.358145+00:00

Scope: offline synchronous extraction + local rule-based invoice parsing (no Celery, DB, network, or semantic indexing)

| Metric | Measured value |
|---|---:|
| total cases | 4 |
| processed cases | 3 |
| processing success rate | 0.75 |
| processing failure rate | 0.25 |
| expected outcome rate | 1.0 |
| labeled fields | 17 |
| field exact match accuracy | 0.882353 |
| field precision nonnull | 1.0 |
| mean elapsed seconds | 0.031503 |
| median elapsed seconds | 0.00159 |
| max elapsed seconds | 0.122623 |
| documents per second | 31.743171 |
| truncated successful cases | 0 |

## Per-file results

| Case | Processed | Expected outcome met | Seconds | Truncated | Error |
|---|---|---|---:|---|---|
| synthetic_flat_invoice | True | True | 0.00287 | False | — |
| synthetic_line_item_invoice | True | True | 0.000309 | False | — |
| synthetic_two_page_pdf | True | True | 0.122623 | False | — |
| corrupt_pdf | False | True | 0.000209 | None | FileDataError: Failed to open file '/mnt/data/phase7build/careguide-document-intelligence/backend/evaluation/docs/broken.pdf'. |

## Limitations

- These measurements are only valid for the labeled manifest on the machine that ran the evaluation.
- Field exact-match scores are computed over explicitly labeled fields, including labeled nulls.
- Timing excludes upload, queue delay, database persistence, and embedding generation.
- Synthetic examples cannot establish real-world invoice accuracy.
- A completed job may still contain truncated text; inspect truncated_successful_cases.
