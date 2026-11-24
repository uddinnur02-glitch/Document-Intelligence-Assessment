"""Phase 9 regression tests. Run in Docker for the real Celery package."""
import os
from io import BytesIO
from pathlib import Path

from app.database import SessionLocal
from app.models import Document, ProcessingEvent
from app import tasks


def test_api_key_guards_all_document_endpoints(client, monkeypatch):
    monkeypatch.setenv('CARE_GUIDE_API_KEY', 'test-only-secret')
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/documents').status_code == 401
    assert client.post('/api/documents', files={'file': ('test.csv', b'a,b\n1,2', 'text/csv')}).status_code == 401
    assert client.get('/api/documents', headers={'X-API-Key': 'incorrect'}).status_code == 401
    assert client.get('/api/documents', headers={'X-API-Key': 'test-only-secret'}).status_code == 200


def test_reject_pdf_with_false_extension(client):
    response = client.post('/api/documents', files={'file': ('fake.pdf', b'not a PDF', 'application/pdf')})
    assert response.status_code == 415


def test_reject_binary_csv(client):
    response = client.post('/api/documents', files={'file': ('fake.csv', b'hello\x00world', 'text/csv')})
    assert response.status_code == 415


def test_reject_fake_xlsx(client):
    response = client.post('/api/documents', files={'file': ('fake.xlsx', b'fake zip', 'application/octet-stream')})
    assert response.status_code == 415


def test_failed_worker_marks_document_failed_and_audits(client, monkeypatch):
    response = client.post('/api/documents', files={'file': ('worker_failure.csv', b'a,b\n1,2', 'text/csv')})
    assert response.status_code == 201
    document_id = response.json()['id']
    def fail(*args, **kwargs):
        raise ValueError('simulated parsing failure')
    monkeypatch.setattr(tasks, 'extract_file', fail)
    tasks.process_document.run(document_id) if hasattr(tasks.process_document, 'run') else tasks.process_document(document_id)
    response = client.get(f'/api/documents/{document_id}')
    assert response.json()['status'] == 'failed'
    assert 'ValueError' in response.json()['error_message']
    history = client.get(f'/api/documents/{document_id}/history')
    assert history.status_code == 200
    assert [row['event'] for row in history.json()][:2] == ['failed', 'processing']


def test_missing_history_returns_404(client):
    assert client.get('/api/documents/missing/history').status_code == 404
