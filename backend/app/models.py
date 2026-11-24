from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now_utc():
    return datetime.now(timezone.utc)

class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default='uploaded', nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

from sqlalchemy import JSON, ForeignKey

class DocumentResult(Base):
    __tablename__ = "document_results"
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), primary_key=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class InvoiceResult(Base):
    __tablename__ = 'invoice_results'
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey('documents.id'), primary_key=True)
    invoice_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_json: Mapped[list] = mapped_column(JSON, nullable=False)
    corrected: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)


class ProcessingEvent(Base):
    """Append-only audit of processing attempts and their outcomes."""
    __tablename__ = 'processing_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey('documents.id'), index=True, nullable=False)
    event: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
