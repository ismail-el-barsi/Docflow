from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    FACTURE = "facture"
    DEVIS = "devis"
    ATTESTATION = "attestation"
    AUTRE = "autre"


class ProcessingStatus(StrEnum):
    UPLOADED = "uploaded"      # Bronze
    PROCESSING = "processing"
    EXTRACTED = "extracted"    # Silver
    CURATED = "curated"        # Gold
    ERROR = "error"


class UploadedDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    original_filename: str
    file_size: int
    mime_type: str = "application/pdf"
    upload_at: datetime = Field(default_factory=datetime.utcnow)
    status: ProcessingStatus = ProcessingStatus.UPLOADED
    error_message: str | None = None
    uploaded_by: str | None = None  # user_id (MongoDB ObjectId)


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    status: ProcessingStatus
    document_type: DocumentType | None = None
    upload_at: datetime
    error_message: str | None = None
    uploaded_by: str | None = None
