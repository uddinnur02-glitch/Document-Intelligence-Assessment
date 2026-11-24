"""Celery job owns processing; database records are updated independently of requests."""
import os
from pathlib import Path
from celery import Celery
from sqlalchemy import select, delete

from .database import SessionLocal
from .models import Document, DocumentResult, InvoiceResult, DocumentChunk, ProcessingEvent
from .processing import extract_file
from .invoices import rule_extract, llm_extract, validate_invoice

celery_app = Celery("careguide", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_backend=None,
                       worker_prefetch_multiplier=1, task_acks_late=True, worker_max_tasks_per_child=20)

@celery_app.task(name="app.tasks.process_document", bind=True, soft_time_limit=600, time_limit=660)
def process_document(self, document_id: str):
    try:
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            if document is None:
                return
            document.status = "processing"
            document.error_message = None
            db.add(ProcessingEvent(document_id=document_id, event='processing'))
            db.commit()
            filepath = Path(os.getenv("UPLOAD_DIR", "/app/uploads")) / document.stored_filename
            filename = document.original_filename
        result = extract_file(str(filepath), filename)
        # A missing or failing external LLM must not prevent local extraction.
        invoice = rule_extract(result)
        try:
            enhanced = llm_extract(result)
            if enhanced is not None:
                invoice = enhanced
                # Preserve source coverage and extraction limitations across LLM enhancement.
                invoice['source_coverage'] = rule_extract(result).get('source_coverage')
                if result.get('truncated'):
                    invoice['warnings'].append('Source extraction was truncated')
        except Exception as error:
            invoice['warnings'].append('Optional LLM unavailable; local rules used')
        extracted_text = result.get("text") or ""
        chunk_texts = [extracted_text[offset:offset+2000]
                       for offset in range(0, len(extracted_text), 1800)]
        vectors = [None] * len(chunk_texts)
        if os.getenv("SEMANTIC_ENABLED", "false").lower() == "true" and chunk_texts:
            try:
                from .semantic import embed_texts
                # Batch processing keeps inference memory bounded.
                for offset in range(0, len(chunk_texts), 16):
                    vectors[offset:offset+16] = embed_texts(chunk_texts[offset:offset+16])
            except Exception as error:
                result["semantic_warning"] = ("Semantic index unavailable: " + str(error))[:350]
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            if document:
                result_row = db.get(DocumentResult, document_id)
                if result_row is None:
                    result_row = DocumentResult(document_id=document_id, result_json=result)
                    db.add(result_row)
                else:
                    result_row.result_json = result
                # Rebuild searchable chunks atomically whenever a document is reprocessed.
                # Search is limited to the same bounded extracted text stored in result_json.
                db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
                for idx, chunk in enumerate(chunk_texts):
                    db.add(DocumentChunk(document_id=document_id, chunk_index=idx,
                                         content=chunk, embedding=vectors[idx]))
                supplier=invoice['fields'].get('supplier_name')
                number=invoice['fields'].get('invoice_number')
                duplicate=False
                if supplier and number:
                    other_rows=db.scalars(select(InvoiceResult).where(InvoiceResult.document_id != document_id)).all()
                    duplicate=any(
                        str(((r.invoice_json or {}).get('fields') or {}).get('supplier_name') or '').casefold()
                        == str(supplier).casefold()
                        and str(((r.invoice_json or {}).get('fields') or {}).get('invoice_number') or '').casefold()
                        == str(number).casefold()
                        for r in other_rows
                    )
                problems=validate_invoice(invoice,duplicate=duplicate)
                invoice_row=db.get(InvoiceResult,document_id)
                if invoice_row is None:
                    db.add(InvoiceResult(document_id=document_id,invoice_json=invoice,validation_json=problems))
                else:
                    invoice_row.invoice_json=invoice
                    invoice_row.validation_json=problems
                    invoice_row.corrected=False
                document.status = "completed"
                document.error_message = None
                db.add(ProcessingEvent(document_id=document_id, event='completed'))
                db.commit()

    except Exception as error:
        # Unexpected failures in extraction, invoice detection, indexing or DB commits
        # must not leave a document indefinitely marked 'processing'.
        import logging
        logging.getLogger(__name__).exception('Document processing failed: %s', document_id)
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            if document is not None:
                document.status = 'failed'
                document.error_message = (type(error).__name__ + ': ' + str(error))[:1000]
                db.add(ProcessingEvent(document_id=document_id, event='failed',
                                       message=document.error_message))
                db.commit()
        return
