"""Phase 8: tests the actual spreadsheet rows rather than the UI preview."""
import csv
from pathlib import Path
import pytest
from app.processing import extract_file
from app.invoices import rule_extract
from app.reconciliation import reconcile


def _make_csv(path, *, change_last=False, quantity=2, rows=28):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['Invoice Number', 'B-2026-001'])
        writer.writerow(['Invoice Date', '2026-11-24'])
        writer.writerow(['Supplier', 'Medical Supply Ltd'])
        writer.writerow(['Customer', 'Care Clinic'])
        writer.writerow(['Currency', 'USD'])
        writer.writerow(['Description', 'Qty', 'Unit Price', 'Amount'])
        for i in range(rows):
            qty = quantity if i == rows - 1 and change_last else 1
            writer.writerow([f'Item {i+1}', qty, '5.00', f'{qty*5:.2f}'])
        writer.writerow(['Subtotal', '', '', ''])


def _invoice(path):
    result = extract_file(str(path), path.name)
    return result, rule_extract(result)


def test_reconciles_rows_beyond_preview(tmp_path):
    a, b = tmp_path/'a.csv', tmp_path/'b.csv'
    _make_csv(a)
    _make_csv(b, change_last=True)
    result_a, invoice_a = _invoice(a)
    _, invoice_b = _invoice(b)
    assert len(result_a['sheets'][0]['preview']) == 20
    assert len(invoice_a['line_items']) == 28
    assert invoice_a['line_items'][-1]['evidence']['row'] == 34
    compared = reconcile(invoice_a, invoice_b)
    assert compared['line_item_summary'] == {'matched':27, 'mismatched':1,'unpaired':0}
    assert compared['reconciliation_status'] == 'review_required'


def test_unit_price_change_is_mismatch_not_unpaired(tmp_path):
    a, b = tmp_path/'a.csv', tmp_path/'b.csv'
    _make_csv(a, rows=2)
    _make_csv(b, rows=2)
    text = b.read_text()
    b.write_text(text.replace('Item 2,1,5.00,5.00', 'Item 2,1,6.00,6.00'))
    _, invoice_a = _invoice(a)
    _, invoice_b = _invoice(b)
    compared = reconcile(invoice_a, invoice_b)
    assert compared['line_item_summary'] == {'matched': 1,'mismatched':1,'unpaired':0}


def test_incomplete_source_cannot_be_full_match(tmp_path, monkeypatch):
    a, b = tmp_path/'a.csv', tmp_path/'b.csv'
    _make_csv(a)
    _make_csv(b)
    monkeypatch.setattr('app.processing.MAX_CHARS', 40)
    result_a, invoice_a = _invoice(a)
    _, invoice_b = _invoice(b)
    assert result_a['truncated']
    assert len(invoice_a['line_items']) == 28  # extracted from streaming rows despite text cap
    assert reconcile(invoice_a,invoice_b)['reconciliation_status']=='incomplete'


def test_unreadable_data_row_requires_manual_review(tmp_path):
    p = tmp_path/'bad-row.csv'
    _make_csv(p, rows=2)
    p.write_text(p.read_text().replace('Item 2,1,5.00,5.00','Item 2,unknown,5.00,5.00'))
    _, invoice = _invoice(p)
    assert len(invoice['line_items']) == 1
    assert invoice['source_coverage']['table_incomplete']
    assert any('could not be parsed' in w for w in invoice['warnings'])


def test_multiple_sheets_xlsx_and_row_index(tmp_path):
    openpyxl = pytest.importorskip('openpyxl')
    path = tmp_path/'book.xlsx'
    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = 'First'
    first.append(['Description', 'Qty', 'Unit Price', 'Amount'])
    for i in range(32):
        first.append([f'Gloves {i}',1,5,5])
    second = workbook.create_sheet('Second')
    second.append(['Description', 'Qty', 'Unit Price', 'Amount'])
    second.append(['Bandages',3,2,6])
    workbook.save(path)
    extracted, inv = _invoice(path)
    assert len(inv['line_items']) == 33
    assert len(extracted['table_coverage']) == 2
    assert inv['line_items'][-1]['evidence']['source'] == 'sheet:Second'
