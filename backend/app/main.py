import hashlib
import hmac
import zipfile
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from fastapi import Request
from fastapi.responses import JSONResponse
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, or_, inspect, text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Document, DocumentResult, InvoiceResult, DocumentChunk, ProcessingEvent
from .schemas import DocumentOut, ProcessingResultOut
from .invoices import FIELDS, normalize_fields, validate_invoice, compare_invoices
from .reconciliation import reconcile
from pydantic import BaseModel, ConfigDict

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.xlsx', '.xls', '.csv'}
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '20'))
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', str(Path(__file__).resolve().parents[1] / 'uploads')))

@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # Safe, additive prototype upgrade for existing Phase 1–5 databases.
    # For production, replace this with versioned Alembic migrations.
    with engine.begin() as conn:
        columns = {column['name'] for column in inspect(conn).get_columns('document_chunks')}
        if 'embedding' not in columns:
            if engine.dialect.name == 'postgresql':
                conn.execute(text('ALTER TABLE document_chunks ADD COLUMN embedding JSON'))
            elif engine.dialect.name == 'sqlite':
                conn.execute(text('ALTER TABLE document_chunks ADD COLUMN embedding JSON'))
            else:
                raise RuntimeError('Unsupported database for Phase 6 automatic upgrade')
    yield

app = FastAPI(title='Care Guide Document Intelligence API', version='0.1.0', lifespan=lifespan)
origins = [item.strip() for item in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST', 'PUT', 'OPTIONS'], allow_headers=['*'])

@app.middleware('http')
async def guard_api(request: Request, call_next):
    """Single-user demo API key; configure CARE_GUIDE_API_KEY for protection.

    This is not multi-user authentication or per-document authorization.
    """
    expected = os.getenv('CARE_GUIDE_API_KEY', '')
    if expected and request.url.path.startswith('/api/') and request.url.path != '/api/health' and request.method != 'OPTIONS':
        provided = request.headers.get('X-API-Key', '')
        if not hmac.compare_digest(provided.encode(), expected.encode()):
            return JSONResponse({'detail': 'API key missing or invalid'}, status_code=401)
    return await call_next(request)


def validate_file_signature(filename: str, path: Path):
    """Verify simple container signatures after streamed upload, before database commit."""
    ext = Path(filename).suffix.lower()
    with path.open('rb') as f:
        sample = f.read(1024 * 1024)
    if ext == '.pdf' and not sample.startswith(b'%PDF-'):
        raise HTTPException(415, 'PDF signature invalid')
    if ext in {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}:
        try:
            with Image.open(path) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(415, 'Image signature invalid')
    if ext == '.xlsx':
        if not zipfile.is_zipfile(path):
            raise HTTPException(415, 'XLSX container invalid')
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if len(names) > 10000 or not {'[Content_Types].xml', 'xl/workbook.xml'}.issubset(names):
                    raise HTTPException(415, 'XLSX workbook structure invalid')
        except zipfile.BadZipFile:
            raise HTTPException(415, 'XLSX container invalid')
    if ext == '.xls' and not sample.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
        raise HTTPException(415, 'XLS signature invalid')
    if ext == '.csv' and b'\x00' in sample:
        raise HTTPException(415, 'CSV contains binary NUL bytes')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'phase': 9}

@app.post('/api/documents', response_model=DocumentOut, status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    original_name = Path((file.filename or '').replace(chr(92), '/')).name
    ext = Path(original_name).suffix.lower()
    if not original_name or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail='Unsupported file type')

    if MAX_UPLOAD_MB < 1 or MAX_UPLOAD_MB > 500:
        raise HTTPException(500, 'Invalid server upload limit')
    doc_id = str(uuid.uuid4())
    stored_name = f'{doc_id}{ext}'
    destination = UPLOAD_DIR / stored_name
    sha = hashlib.sha256()
    total = 0
    try:
        with destination.open('wb') as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f'File exceeds {MAX_UPLOAD_MB} MB limit')
                sha.update(chunk)
                target.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail='Empty files are not accepted')
        validate_file_signature(original_name, destination)
        document = Document(
            id=doc_id, original_filename=original_name[:255], stored_filename=stored_name,
            content_type=file.content_type or 'application/octet-stream',
            size_bytes=total, sha256=sha.hexdigest(), status='uploaded',
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

@app.get('/api/documents', response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.scalars(select(Document).order_by(Document.created_at.desc()).limit(100)).all()

@app.get('/api/search')
def keyword_search(q: str, limit: int = 20, db: Session = Depends(get_db)):
    """Case-insensitive literal substring search across filenames and processed text.

    Simple SQL LIKE, not a full-text index. For production, add GIN/tsvector.
    """
    term = q.strip()
    if len(term) < 2 or len(term) > 100:
        raise HTTPException(status_code=422, detail='Search must contain 2–100 characters')
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=422, detail='limit must be between 1 and 50')
    # Escape SQL LIKE wildcards to ensure an ordinary literal-text search.
    pattern = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    matches = db.execute(
        select(Document, DocumentChunk.content)
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .where(or_(Document.original_filename.ilike(pattern, escape='\\'),
                   DocumentChunk.content.ilike(pattern, escape='\\')))
        .order_by(Document.created_at.desc())
    ).all()
    results, seen = [], set()
    for document, content in matches:
        if document.id in seen:
            continue
        seen.add(document.id)
        snippet = ''
        if content:
            location = content.casefold().find(term.casefold())
            if location >= 0:
                snippet = content[max(0, location-75):location+len(term)+110]
        results.append({'document_id': document.id,
                        'filename': document.original_filename,
                        'status': document.status,
                        'snippet': snippet})
        if len(results) == limit:
            break
    return {'query': term, 'results': results, 'count': len(results),
            'note': 'Literal keyword search on filenames and stored text, not semantic search. '
                    'Older documents require reprocessing to populate the search index. '
                    'Stored extraction text may be truncated.'}


@app.get('/api/search/semantic')
def semantic_search(q: str, limit: int = 10, db: Session = Depends(get_db)):
    """Rank locally embedded text chunks; no filename-only matches.

    Only previously indexed documents are searched. The first model use may
    download model weights; contact to external model repository is required.
    """
    term = q.strip()
    if not 2 <= len(term) <= 200 or not 1 <= limit <= 30:
        raise HTTPException(status_code=422, detail='q must be 2–200 chars; limit 1–30')
    rows = db.execute(select(Document, DocumentChunk)
                      .join(DocumentChunk, Document.id == DocumentChunk.document_id)
                      .where(Document.status == 'completed', DocumentChunk.embedding.is_not(None))
                      .limit(2000)).all()
    if not rows:
        return {'query': term, 'results': [], 'count': 0,
                'note': 'No semantic embeddings indexed. Reprocess documents with SEMANTIC_ENABLED=true; older uploads are not automatically indexed.'}
    try:
        from .semantic import embed_texts, cosine
        query_vector = embed_texts([term])[0]
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Local embedding model unavailable; check logs and model download') from exc
    best = {}
    for document, chunk in rows:
        score = cosine(query_vector, chunk.embedding)
        if document.id not in best or best[document.id]['score'] < score:
            best[document.id] = {'document_id':document.id, 'filename':document.original_filename,
                                 'status':document.status, 'snippet':chunk.content[:250],
                                 'score':round(score, 4), 'chunk_index':chunk.chunk_index}
    ranked = sorted(best.values(),key=lambda item:item['score'],reverse=True)[:limit]
    return {'query':term, 'results':ranked, 'count':len(ranked),
            'note':'Local embedding cosine similarity on at most 2,000 indexed chunks; scores are relevance, not verified accuracy. Large corpora require pgvector/HNSW.'}


@app.get('/api/documents/{document_id}', response_model=DocumentOut)
def document_status(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='Document not found')
    return document


@app.post('/api/documents/{document_id}/process', response_model=DocumentOut, status_code=202)
def queue_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='Document not found')
    if document.status in {'queued', 'processing'}:
        raise HTTPException(status_code=409, detail='Document already processing')
    old_status = document.status
    document.status = 'queued'
    document.error_message = None
    db.add(ProcessingEvent(document_id=document_id, event='queued'))
    db.commit()
    from .tasks import process_document
    try:
        process_document.delay(document_id)
    except Exception as exc:
        document.status = old_status
        document.error_message = 'Failed to submit processing job'
        db.add(ProcessingEvent(document_id=document_id, event='failed', message='Queue submission failed'))
        db.commit()
        raise HTTPException(status_code=503, detail='Processing queue unavailable') from exc
    db.refresh(document)
    return document


@app.get('/api/documents/{document_id}/result', response_model=ProcessingResultOut)
def document_result(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='Document not found')
    row = db.get(DocumentResult, document_id)
    return ProcessingResultOut(document_id=document_id, status=document.status,
                               result=row.result_json if row and document.status == 'completed' else None,
                               error_message=document.error_message)


class InvoiceCorrection(BaseModel):
    # Full replacement fields on a corrected invoice. Unknown keys forbidden.
    model_config = ConfigDict(extra='forbid')
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: str | None = None
    tax: str | None = None
    total: str | None = None
    currency: str | None = None


def _invoice_or_404(db: Session, document_id: str):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='Document not found')
    row = db.get(InvoiceResult, document_id)
    if row is None:
        raise HTTPException(status_code=409, detail='Document not processed yet')
    return row


@app.get('/api/documents/{document_id}/invoice')
def get_invoice(document_id: str, db: Session = Depends(get_db)):
    row = _invoice_or_404(db, document_id)
    return {'document_id': document_id, 'invoice': row.invoice_json,
            'validation': row.validation_json, 'manual_correction': row.corrected}


@app.put('/api/documents/{document_id}/invoice')
def correct_invoice(document_id: str, payload: InvoiceCorrection, db: Session = Depends(get_db)):
    row = _invoice_or_404(db, document_id)
    # Explicit manual edits must preserve the existing line items and the extraction history.
    existing = dict(row.invoice_json)
    updated_fields = dict(existing['fields'])
    updated_fields.update(payload.model_dump(exclude_unset=True))
    normalized = normalize_fields({'line_items':existing.get('line_items',[]), **updated_fields},method='manual')
    if updated_fields.get('invoice_date') and not normalized['fields']['invoice_date']:
        raise HTTPException(status_code=422, detail='Invalid date; expected YYYY-MM-DD')
    for key in ('subtotal','tax','total'):
        if updated_fields.get(key) is not None and normalized['fields'][key] is None:
            raise HTTPException(status_code=422, detail=f'Invalid numeric value for {key}')
    normalized['warnings'] = ['Manually corrected; compare against original uploaded document']
    normalized['source_coverage'] = existing.get('source_coverage', {})
    row.invoice_json = normalized
    row.validation_json = validate_invoice(normalized)
    row.corrected = True
    db.commit()
    return {'document_id':document_id,'invoice':row.invoice_json,'validation':row.validation_json,'manual_correction':True}


@app.get('/api/compare')
def compare_documents(left_id: str, right_id: str, db: Session = Depends(get_db)):
    if left_id==right_id: raise HTTPException(status_code=400,detail='Choose two distinct documents')
    left=_invoice_or_404(db,left_id)
    right=_invoice_or_404(db,right_id)
    return {'left_id':left_id,'right_id':right_id, **reconcile(left.invoice_json,right.invoice_json)}


@app.get('/api/documents/{document_id}/history')
def processing_history(document_id: str, db: Session = Depends(get_db)):
    if db.get(Document, document_id) is None:
        raise HTTPException(404, 'Document not found')
    rows = db.scalars(select(ProcessingEvent).where(ProcessingEvent.document_id == document_id)
                      .order_by(ProcessingEvent.id.desc()).limit(100)).all()
    return [{'event': row.event, 'message': row.message, 'created_at': row.created_at.isoformat()}
            for row in rows]
