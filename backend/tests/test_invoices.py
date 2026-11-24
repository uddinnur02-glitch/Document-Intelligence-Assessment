from app.invoices import rule_extract, validate_invoice, compare_invoices, normalize_fields
from app.models import InvoiceResult
from app.database import SessionLocal

SAMPLE = '''Invoice No: INV-2026-004
Invoice Date: 2026-11-20
Supplier: ABC Trading Ltd
Bill To: Cottage Home Care
Subtotal: $1,250.00
Tax: $125.00
Grand Total: $1,400.00
Currency: USD'''

def test_extract_invoice():
    invoice=rule_extract({'text':SAMPLE,'sheets':[]})
    assert invoice['fields']['invoice_number']=='INV-2026-004'
    assert invoice['fields']['supplier_name']=='ABC Trading Ltd'
    assert invoice['fields']['total']=='1400.00'
    assert invoice['fields']['currency']=='USD'

def test_validation_mismatch():
    findings=validate_invoice(rule_extract({'text':SAMPLE}))
    assert 'total_mismatch' in [v['code'] for v in findings]

def test_missing_not_fabricated():
    fields=rule_extract({'text':'random content'})['fields']
    assert fields['invoice_number'] is None
    assert fields['total'] is None

def test_decimal_exact_arithmetic():
    invoice=normalize_fields({'invoice_number':'INV-2','invoice_date':'2026-11-20','supplier_name':'A',
       'subtotal':'0.10','tax':'0.20','total':'0.30'})
    assert 'total_mismatch' not in [v['code'] for v in validate_invoice(invoice)]

def test_line_item_mismatch():
    invoice=normalize_fields({'subtotal':'10','tax':'0','total':'10',
       'line_items':[{'description':'Widget','quantity':'2','unit_price':'3','amount':'9'}]})
    codes=[x['code'] for x in validate_invoice(invoice)]
    assert 'line_item_mismatch' in codes
    assert 'line_sum_mismatch' in codes

def test_compare():
    a=normalize_fields({'invoice_number':'A','total':'10'})
    b=normalize_fields({'invoice_number':'A','total':'11'})
    result=compare_invoices(a,b)
    assert result['mismatches']==1

def test_invoice_routes(client):
    resp=client.post('/api/documents',files={'file':('inv.csv',b'a,b\n1,2','text/csv')})
    docid=resp.json()['id']
    assert client.get(f'/api/documents/{docid}/invoice').status_code==409
    with SessionLocal() as db:
        invoice=rule_extract({'text':SAMPLE})
        db.add(InvoiceResult(document_id=docid, invoice_json=invoice,
                             validation_json=validate_invoice(invoice)))
        db.commit()
    loaded=client.get(f'/api/documents/{docid}/invoice')
    assert loaded.status_code==200
    assert loaded.json()['invoice']['fields']['total']=='1400.00'
    corrected=client.put(f'/api/documents/{docid}/invoice',json={'total':'1375.00'})
    assert corrected.status_code==200
    assert not any(x['code']=='total_mismatch' for x in corrected.json()['validation'])
    assert client.put(f'/api/documents/{docid}/invoice',json={'total':'abc'}).status_code==422
    assert client.get(f'/api/compare?left_id={docid}&right_id={docid}').status_code==400
