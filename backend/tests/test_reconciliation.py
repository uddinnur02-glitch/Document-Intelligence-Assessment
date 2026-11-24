from pathlib import Path
from app.processing import extract_file
from app.invoices import rule_extract, validate_invoice
from app.reconciliation import reconcile, extract_line_items

EXAMPLES = Path(__file__).resolve().parents[2] / 'examples'

def _invoice(filename):
    result=extract_file(str(EXAMPLES/filename),filename)
    return rule_extract(result)

def test_csv_line_items():
    invoice=_invoice('phase4_invoice_lineitems.csv')
    assert len(invoice['line_items'])==2
    assert invoice['line_items'][0]['description']=='Disposable gloves'
    assert invoice['line_items'][1]['quantity']=='5.00'
    assert not any(v['code'] in {'line_sum_mismatch','line_item_mismatch','total_mismatch'} for v in validate_invoice(invoice))

def test_reconciliation_mismatch():
    left=_invoice('phase4_invoice_lineitems.csv')
    right=_invoice('phase4_invoice_lineitems_mismatch.csv')
    result=reconcile(left,right)
    assert result['line_item_summary']=={'matched':1,'mismatched':1,'unpaired':0}
    assert result['reconciliation_status']=='review_required'
    assert result['mismatches']>=3

def test_missing_table_does_not_invent_items():
    data={'kind':'pdf','pages':[{'page':1,'text':'Pens 3 10 30'}], 'sheets':[]}
    assert extract_line_items(data)[0]==[]

def test_explicit_pipe_delimited_pdf_table():
    data={'kind':'pdf','pages':[{'page':1,'text':'Description | Qty | Unit Price | Amount\nPens | 3 | 10.00 | 30.00'}], 'sheets':[]}
    items,_=extract_line_items(data)
    assert len(items)==1 and items[0]['amount']=='30.00'

def test_missing_line_items_is_incomplete():
    left=_invoice('phase4_invoice_lineitems.csv')
    empty={'fields':left['fields'],'line_items':[]}
    assert reconcile(left,empty)['reconciliation_status']=='incomplete'

def test_inconsistent_line_amount_is_flagged():
    invoice=_invoice('phase4_invoice_lineitems.csv')
    invoice['line_items'][0]['amount']='101.00'
    codes=[p['code'] for p in validate_invoice(invoice)]
    assert 'line_item_mismatch' in codes
    assert 'line_sum_mismatch' in codes
