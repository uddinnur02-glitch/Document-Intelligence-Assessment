def test_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'

def test_upload_and_status(client):
    response = client.post('/api/documents', files={'file': ('invoice.csv', b'invoice,total\nINV-1,100\n', 'text/csv')})
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['status'] == 'uploaded'
    assert data['original_filename'] == 'invoice.csv'
    assert data['size_bytes'] > 0
    assert client.get(f"/api/documents/{data['id']}").json()['id'] == data['id']
    assert any(x['id'] == data['id'] for x in client.get('/api/documents').json())

def test_invalid_extension(client):
    response = client.post('/api/documents', files={'file': ('run.exe', b'bad', 'application/octet-stream')})
    assert response.status_code == 415

def test_empty_file(client):
    response = client.post('/api/documents', files={'file': ('empty.csv', b'', 'text/csv')})
    assert response.status_code == 400

def test_missing_document(client):
    assert client.get('/api/documents/not-real').status_code == 404

def test_result_not_processed(client):
    response=client.post('/api/documents', files={'file':('result.csv', b'a,b\n1,2', 'text/csv')})
    doc_id=response.json()['id']
    result=client.get(f'/api/documents/{doc_id}/result')
    assert result.status_code==200
    assert result.json()['status']=='uploaded'
    assert result.json()['result'] is None


def test_process_missing_document(client):
    assert client.post('/api/documents/not-here/process').status_code==404
