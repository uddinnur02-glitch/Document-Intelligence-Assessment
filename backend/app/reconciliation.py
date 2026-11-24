"""Evidence-aware reconciliation. No undocumented full-document claims.

Streaming sheet collector uses all rows up to explicit configurable limits.
PDF tables remain heuristic, OCR table recovery is not guaranteed.
"""
import os
import re
from collections import defaultdict
from decimal import Decimal

ALIASES = {
    'description': {'description', 'item', 'item description', 'product', 'service'},
    'quantity': {'qty', 'quantity', 'units'},
    'unit_price': {'unit price', 'unit cost', 'rate', 'price per unit'},
    'amount': {'amount', 'line total', 'line amount', 'extended price', 'extended amount'},
}
MAX_LINE_ITEMS = int(os.getenv('MAX_LINE_ITEMS', '5000'))


def canonical(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).strip()


def parse_amount(value):
    from .invoices import _money
    return _money(value)


def _indices(row):
    normalized = [canonical(c) for c in row]
    positions = {field: next((i for i, name in enumerate(normalized) if name in names), None)
                 for field, names in ALIASES.items()}
    return positions if all(x is not None for x in positions.values()) else None


class StreamingLineItems:
    """Stateful parser that consumes sheet rows as they arrive, without a preview limit."""
    def __init__(self, source):
        self.source = source
        self.indices = None
        self.items = []
        self.total_items = 0
        self.limit_reached = False
        self.headers_found = False
        self.stopped = False
        self.invalid_rows = 0

    def feed(self, row, row_number):
        if self.stopped:
            return
        if self.indices is None:
            self.indices = _indices(row)
            if self.indices:
                self.headers_found = True
            return
        if len(row) <= max(self.indices.values()):
            if any(str(x or '').strip() for x in row):
                self.invalid_rows += 1
            return
        def cell(key):
            return str(row[self.indices[key]] or '').strip()
        desc = cell('description')
        if canonical(desc) in {'subtotal', 'sub total', 'tax', 'vat', 'total', 'grand total'}:
            self.stopped = True
            return
        if not desc:
            if any(cell(k) for k in ('quantity', 'unit_price', 'amount')):
                self.invalid_rows += 1
            return
        values = {k: parse_amount(cell(k)) for k in ('quantity', 'unit_price', 'amount')}
        if any(v is None for v in values.values()):
            self.invalid_rows += 1
            return
        self.total_items += 1
        if len(self.items) < MAX_LINE_ITEMS:
            self.items.append({'description': desc[:255],
                               **{k: str(v) for k, v in values.items()},
                               'evidence': {'source': self.source, 'row': row_number}})
        else:
            self.limit_reached = True

    def coverage(self):
        return {'source': self.source, 'headers_found': self.headers_found,
                'parsed_items': self.total_items, 'invalid_rows': self.invalid_rows,
                'limit_reached': self.limit_reached}


def _parse_rows(rows, source):
    parser = StreamingLineItems(source)
    for number, row in enumerate(rows, 1):
        parser.feed(row, number)
    return parser.items, parser.coverage()


def extract_line_items(extracted):
    items = []
    warnings = []
    coverage = []
    kind = extracted.get('kind')
    if kind in {'csv', 'spreadsheet'} and 'structured_line_items' in extracted:
        items.extend(extracted['structured_line_items'])
        coverage.extend(extracted.get('table_coverage') or [])
        if any(c.get('invalid_rows') for c in coverage):
            warnings.append('Some nonempty line-item rows could not be parsed and require review.')
        if any(c.get('limit_reached') for c in coverage):
            warnings.append(f'Line-item results exceeded the {MAX_LINE_ITEMS} item limit per sheet.')
        if not any(c.get('headers_found') for c in coverage):
            warnings.append('No recognizable complete line-item header found in spreadsheet.')
    else:
        # Backward compatibility for old stored results: these may be preview-only.
        for sheet in extracted.get('sheets') or []:
            parsed, detail = _parse_rows(sheet.get('preview') or [], 'sheet:' + str(sheet.get('name', 'unknown')))
            items.extend(parsed)
            coverage.append(detail)
            if sheet.get('rows', 0) > len(sheet.get('preview') or []):
                warnings.append('Legacy sheet extraction only has preview rows; reprocess for full row reconciliation.')
    if kind == 'pdf':
        for page_tables in extracted.get('pdf_tables') or []:
            for table in page_tables.get('tables') or []:
                parsed, detail = _parse_rows(table.get('rows') or [],
                    f"pdf-page:{page_tables['page']}-table:{table['table']}")
                items.extend(parsed)
                coverage.append(detail)
                if table.get('limited'):
                    warnings.append('PDF table rows were capped; financial reconciliation is incomplete.')
        for page in extracted.get('pages') or []:
            lines = [line.strip() for line in (page.get('text') or '').splitlines()]
            tabular = [[part.strip() for part in re.split(r'\s*\|\s*|\t', line)]
                       for line in lines if '|' in line or '\t' in line]
            parsed, detail = _parse_rows(tabular, 'pdf-page:' + str(page.get('page')))
            # Prevent double-counting the same rows when native tables also found.
            if not (extracted.get('pdf_tables') or []) or not any(
                p.get('page') == page.get('page') and p.get('tables') for p in extracted.get('pdf_tables', [])):
                items.extend(parsed)
            coverage.append(detail)
    if extracted.get('truncated'):
        warnings.append('Source extraction was truncated; results cannot prove complete reconciliation.')
    if len(items) > MAX_LINE_ITEMS:
        warnings.append(f'Combined line items exceeded {MAX_LINE_ITEMS}; items were capped.')
    return items[:MAX_LINE_ITEMS], list(dict.fromkeys(warnings))


def _item_key(item):
    # Compare the same product even when its unit price changes.
    return canonical(item.get('description'))


def reconcile(left, right):
    from .invoices import compare_invoices
    base = compare_invoices(left, right)
    a, b = left.get('line_items') or [], right.get('line_items') or []
    coverage_left = left.get('source_coverage') or {}
    coverage_right = right.get('source_coverage') or {}
    risks = []
    for label, doc in [('Left', left), ('Right', right)]:
        cov = doc.get('source_coverage') or {}
        if not cov:
            risks.append(f'{label} document has no extraction coverage metadata; reprocess it.')
        elif cov.get('truncated') or cov.get('table_incomplete') or cov.get('limit_reached'):
            risks.append(f'{label} extraction is truncated, limited, or contains unparsed line-item rows.')
        if doc.get('warnings'):
            risks.append(f'{label} has extraction warnings requiring review.')
    if not a or not b:
        return {**base, 'line_items': [],
                'line_item_summary': {'matched': 0, 'mismatched': 0, 'unpaired': 0},
                'reconciliation_status': 'incomplete',
                'limitations': list(dict.fromkeys(risks + [
                    'One or both documents have no reliably extracted line items.',
                    'No complete financial reconciliation is established.']))}
    left_groups, right_groups = defaultdict(list), defaultdict(list)
    for item in a:
        left_groups[_item_key(item)].append(item)
    for item in b:
        right_groups[_item_key(item)].append(item)
    differences = []
    for key in sorted(set(left_groups) | set(right_groups)):
        ll, rr = left_groups.get(key, []), right_groups.get(key, [])
        for index in range(max(len(ll), len(rr))):
            li = ll[index] if index < len(ll) else None
            ri = rr[index] if index < len(rr) else None
            if li is None or ri is None:
                status = 'unpaired'
            elif all(parse_amount(li.get(field)) == parse_amount(ri.get(field))
                     for field in ('quantity', 'unit_price', 'amount')):
                status = 'match'
            else:
                status = 'mismatch'
            differences.append({'description': (li or ri).get('description'),
                                'left': li, 'right': ri, 'status': status})
    summary = {status: sum(d['status'] == status for d in differences)
               for status in ('match', 'mismatch', 'unpaired')}
    missing_fields = any(x['status'] == 'missing' for x in base['fields'])
    mismatch = bool(summary['mismatch'] or summary['unpaired'] or base['mismatches'])
    # Matched means only that the EXTRACTED data matches; avoid claiming full verification.
    if risks:
        result_status = 'incomplete'
    elif mismatch or missing_fields:
        result_status = 'review_required'
    else:
        result_status = 'matched_extracted_data'
    return {**base, 'line_items': differences,
            'line_item_summary': {'matched': summary['match'], 'mismatched': summary['mismatch'],
                                  'unpaired': summary['unpaired']},
            'reconciliation_status': result_status,
            'source_coverage': {'left': coverage_left, 'right': coverage_right},
            'limitations': list(dict.fromkeys(risks + [
                'Results compare parsed records, not invoice authenticity.',
                'Repeated descriptions are paired in source order; review ambiguous duplicates.',
                'Scanned PDF tables or unusual layouts may not be fully recovered.']))}
