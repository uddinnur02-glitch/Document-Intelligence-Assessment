from pathlib import Path
import fitz
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Document, DocumentChunk
from app.processing import extract_file
from app.reconciliation import extract_line_items
from app.semantic import cosine


def test_cosine():
    assert cosine([1., 0.], [1., 0.]) == 1
    assert cosine([1., 0.], [0., 1.]) == 0
    assert cosine([1.], [1., 0.]) == 0


def test_semantic_search_indexed(client, monkeypatch):
    from app import semantic
    monkeypatch.setattr(semantic, 'embed_texts', lambda texts: [[1., 0.]] if len(texts) == 1 else [])
    upload=client.post('/api/documents', files={'file':('vector_sample.csv',b'amount,150\n', 'text/csv')})
    assert upload.status_code == 201
    doc_id=upload.json()['id']
    with SessionLocal() as db:
        doc=db.get(Document,doc_id)
        doc.status='completed'
        db.add(DocumentChunk(document_id=doc_id,chunk_index=0,content='Payment amount on supplier invoice',embedding=[0.8,0.6]))
        db.commit()
    result=client.get('/api/search/semantic',params={'q':'payment request'})
    assert result.status_code==200
    assert result.json()['results'][0]['document_id']==doc_id
    assert result.json()['results'][0]['score']==0.8


def test_semantic_query_validation(client):
    assert client.get('/api/search/semantic',params={'q':'x'}).status_code==422


def test_pdf_native_table_detection(tmp_path):
    path=tmp_path/'table.pdf'
    doc=fitz.open()
    page=doc.new_page()
    # A vector PDF grid with recognizable column names.
    cells=[['Description','Quantity','Unit price','Amount'],['Gloves','2','50','100'],['Masks','5','10','50']]
    xs=[40,230,320,420,540]
    ys=[50,78,106,134]
    for x in xs: page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys: page.draw_line((xs[0],y),(xs[-1],y))
    for i,row in enumerate(cells):
        for j,value in enumerate(row):
            page.insert_text((xs[j]+4,ys[i]+18),value,fontsize=10)
    doc.save(path);doc.close()
    result=extract_file(str(path),'table.pdf')
    assert 'pdf_tables' in result
    tables=result['pdf_tables'][0]['tables']
    assert tables, 'Expected native PDF table recognition'
    items,_=extract_line_items(result)
    assert any(i['description']=='Gloves' and i['amount']=='100.00' for i in items)
