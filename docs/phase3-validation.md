# Phase 3 validation and design decisions

## Normalized invoice JSON

```json
{
  "fields": {
    "invoice_number":"INV-2026-004", "invoice_date":"2026-11-20",
    "supplier_name":"ABC Trading Ltd", "customer_name":"Cottage Home Care",
    "subtotal":"1250.00", "tax":"125.00", "total":"1400.00", "currency":"USD"
  },
  "line_items":[],
  "extraction_method":"rules",
  "evidence":{"invoice_number":{"source":"document_text","raw":"INV-2026-004"}},
  "warnings":["Rule-based line-item extraction is not available; use manual review or opt-in LLM extraction."]
}
```

`null` means unknown / not found. Validation findings include `missing_field`, `total_mismatch`, `line_item_mismatch`, `line_sum_mismatch`, `possible_duplicate`, and informational `limited_extraction`.

## Quick demonstration

Upload and process two PDFs or CSV invoices containing explicit labels. View their invoice records and compare them via `/api/compare`. The sample below should flag a total mismatch:

```
Invoice No: INV-2026-004
Invoice Date: 2026-11-20
Supplier: ABC Trading Ltd
Bill To: Cottage Home Care
Subtotal: $1,250.00
Tax: $125.00
Grand Total: $1,400.00
Currency: USD
```

Expected: subtotal + tax = 1,375.00 but total = 1,400.00. Saving total as `1375.00` clears the mismatch; the stored file is unchanged.

## Testing

Run `docker compose exec backend pytest -q`. The Phase 3 test suite exercises rule extraction, missing fields, decimal arithmetic, line-item mismatches, comparisons, correction validation, and the existing Phase 1/2 tests. Actual model extraction accuracy and benchmark throughput are **not** measured in this phase.
