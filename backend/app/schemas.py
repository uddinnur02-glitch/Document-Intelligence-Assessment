from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: str
    error_message: str | None
    created_at: datetime


class ProcessingResultOut(BaseModel):
    document_id: str
    status: str
    result: dict | None = None
    error_message: str | None = None
