# Phase 4 — Line items and reconciliation

## Supported
- Explicit table headers: Description / Item, Quantity / Qty, Unit Price / Rate, Amount / Line Total.
- CSV, XLS, XLSX preview tables, and text-based PDF pages with pipe (`|`) or tab-delimited line items.
- Decimal validation of quantity × unit price and sum of line item amounts against subtotal.
- Cross-document comparison of invoice fields and line items with matched, mismatched and unpaired results.
- Existing `GET /api/compare?left_id=...&right_id=...` returns `line_items`, `line_item_summary`, `reconciliation_status`, and limitations.

## Limitations
- Phase 2 stores only the first **20 rows per spreadsheet sheet** and caps extracted PDF page text at 4,000 characters. As a result, reconciliation is **not exhaustive for large files**.
- Unstructured PDFs without explicit delimiters are **not** parsed into line items. This avoids accidental fabrication.
- Duplicate item names are matched using normalized description and unit price; differing price becomes an unpaired row.
- Repeated descriptions are aligned by encounter order, not a globally optimal matching algorithm.
- No line-item manual edit interface, table bounding boxes, fraud detection or exhaustive PDF-to-Excel cross verification yet.
- Never use this pilot without human review for actual finance decisions.

## Test scenario
1. Upload and process `examples/phase4_invoice_lineitems.csv`.
2. Upload and process `examples/phase4_invoice_lineitems_mismatch.csv`.
3. Open first document, inspect its 2 extracted items.
4. Use Compare fields selecting second document.
5. Expected one mismatched item (Face masks) plus subtotal, tax, total mismatches.
6. Run `docker compose exec backend pytest -q`.

## Next engineering priority
Parse **complete** spreadsheet rows (not previews) into bounded separate storage; build table-aware PDF layout extraction and page-indexed evidence, and add evaluation with real labeled invoices.
