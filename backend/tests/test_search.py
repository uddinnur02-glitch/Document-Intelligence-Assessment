from app.database import SessionLocal
from app.models import Document, DocumentChunk
from app.processing import extract_file


def test_csv_21st_row_is_searchable(tmp_path):
    rows = ['invoice,amount'] + [f'REF-{i},10' for i in range(1, 22)]
    f = tmp_path / 'big.csv'
    f.write_text('\n'.join(rows), encoding='utf-8')
    result = extract_file(str(f), f.name)
    assert len(result['sheets'][0]['preview']) == 20
    assert 'REF-21' in result['text']


def test_search_content_and_filename(client):
    with SessionLocal() as db:
        document = Document(id='123e4567-e89b-12d3-a456-426614174001',
                            original_filename='myreceipt.csv', stored_filename='search.csv',
                            content_type='text/csv', size_bytes=12, sha256='a'*64,
                            status='completed')
        db.add(document)
        db.add(DocumentChunk(document_id=document.id, chunk_index=0,
                             content='Supplier Rainforest Logistics, Total 200'))
        db.commit()
    response = client.get('/api/search', params={'q':'rainforest'})
    assert response.status_code == 200
    assert any(x['filename']=='myreceipt.csv' for x in response.json()['results'])
    assert client.get('/api/search', params={'q':'myreceipt'}).json()['count'] >= 1


def test_search_validates_query(client):
    assert client.get('/api/search', params={'q':'a'}).status_code == 422
    assert client.get('/api/search', params={'q':'hi', 'limit':100}).status_code == 422


def test_search_escapes_wildcards(client):
    assert client.get('/api/search', params={'q':'%%%%'}).status_code == 200
    assert client.get('/api/search', params={'q':'%%%%'}).json()['count'] == 0
