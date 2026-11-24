# Phase 10B — Measured OCR and Invoice Evaluation

Generated (UTC): 2026-11-24T09:39:04.772102+00:00

offline synthetic/consented OCR + rule-based invoice extraction (no API, Celery, DB or network)

| Metric | Measured value |
|---|---:|
| total cases | 5 |
| processed cases | 4 |
| processing success rate | 0.8 |
| expected outcome rate | 1.0 |
| ocr character error rate micro | 0.0 |
| ocr word error rate micro | 0.0 |
| invoice field exact match accuracy | 1.0 |
| labeled invoice fields | 32 |
| mean elapsed seconds | 0.289635 |
| truncated successful cases | 0 |
| page count mismatches | 0 |

## Per-file evidence

| Case | Processed | Time (s) | CER | WER | Truncated | Error |
|---|---|---:|---:|---:|---|---|
| clear_png | True | 0.250814 | 0.0 | 0.0 | False | — |
| degraded_jpeg | True | 0.196494 | 0.0 | 0.0 | False | — |
| tiff_image | True | 0.23205 | 0.0 | 0.0 | False | — |
| scanned_pdf | True | 0.748404 | 0.0 | 0.0 | False | — |
| corrupted_png | False | 0.020412 | None | None | None | UnidentifiedImageError: cannot identify image file '/mnt/data/phase10b_work/careguide-document-intelligence/backend/evaluation/ocr_fixtures/broken_image.png' |

## Limitations

- OCR CER/WER compare normalized text with exact sequence, so line-order differences may increase error.
- 2-page sample uses the first invoice as invoice-field ground truth; OCR text scoring covers both pages.
- Synthetic scans do not establish real-world accuracy or generalization.
- Text is bounded by per-page preview caps; truncated files must be reviewed.
- No timing for upload, Celery, PostgreSQL, model load, indexing or frontend.
