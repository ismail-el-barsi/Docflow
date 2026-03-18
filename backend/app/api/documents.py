"""Routes API pour la gestion des documents."""
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.auth import require_auth
from app.schemas.document import DocumentResponse, ProcessingStatus, UploadedDocument
from app.services.pipeline import curate_all_documents, process_document
from app.storage import datalake

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path("./storage/bronze")
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _is_admin(payload: dict) -> bool:
    return payload.get("role") == "admin"


def _user_owns(document_id: uuid.UUID, user_id: str, user_email: str | None = None) -> bool:
    """Vérifie que le document appartient à l'utilisateur via le bronze record."""
    bronze = datalake.load_bronze(document_id)
    if not bronze:
        return False
    # Priorité : owner_id (ObjectId fiable)
    if bronze.document.owner_id:
        return bronze.document.owner_id == user_id
    # Rétrocompatibilité : anciens docs sans owner_id (uploaded_by = email ou ObjectId)
    owner = bronze.document.uploaded_by
    if owner and owner == user_id:
        return True
    if user_email and owner == user_email:
        return True
    return False


def _format_pipeline_error(exc: Exception) -> str:
    """Normalise un message d'erreur lisible pour le frontend."""
    raw = str(exc).strip()
    message = raw or exc.__class__.__name__
    lower = message.lower()

    if "invalid api key" in lower:
        return "Clé API LLM invalide."
    if "authenticationerror" in lower and "401" in lower:
        return "Erreur d'authentification LLM. Vérifiez la clé API."

    return message


def _is_allowed_upload(file: UploadFile) -> bool:
    content_type = (file.content_type or "").lower()
    if content_type in ALLOWED_MIME_TYPES:
        return True

    if content_type.startswith("image/"):
        return True

    suffix = Path(file.filename or "").suffix.lower()
    return suffix in ALLOWED_EXTENSIONS


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_auth),
) -> list[DocumentResponse]:
    """Upload un ou plusieurs documents et lance leur traitement en arrière-plan."""
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    responses: list[DocumentResponse] = []
    user_id: str = payload["sub"]
    user_display: str = payload.get("full_name") or payload.get("email", user_id)

    for file in files:
        if not _is_allowed_upload(file):
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Type de fichier non supporté : {file.content_type}."
                    " Formats acceptés : PDF, DOC/DOCX, images."
                ),
            )

        content = await file.read()
        doc_id = uuid.uuid4()
        safe_filename = f"{doc_id}_{file.filename}"

        document = UploadedDocument(
            id=doc_id,
            filename=safe_filename,
            original_filename=file.filename or "document.pdf",
            file_size=len(content),
            owner_id=user_id,
            uploaded_by=user_display,
        )

        bronze = datalake.save_bronze(document, content)
        file_path = Path(bronze.file_path)
        background_tasks.add_task(_process_and_curate, document, file_path)

        responses.append(DocumentResponse(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            status=ProcessingStatus.UPLOADED,
            upload_at=document.upload_at,
        ))

    return responses


async def _process_and_curate(document: UploadedDocument, file_path: Path) -> None:
    datalake.update_bronze_status(document.id, ProcessingStatus.PROCESSING)
    try:
        process_document(document, file_path)
        datalake.update_bronze_status(document.id, ProcessingStatus.EXTRACTED)
        curate_all_documents()
        datalake.update_bronze_status(document.id, ProcessingStatus.CURATED)
    except Exception as exc:
        error_message = _format_pipeline_error(exc)
        datalake.update_bronze_status(
            document.id,
            ProcessingStatus.ERROR,
            error_message=error_message,
        )
        logger.exception("Erreur pipeline pour '%s' : %s", document.original_filename, exc)


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(payload: dict = Depends(require_auth)) -> list[DocumentResponse]:
    """Liste les documents — admin : tous, user : seulement les siens."""
    user_id: str = payload["sub"]
    is_admin = _is_admin(payload)

    # Construire les maps depuis les bronze records (source de vérité pour upload)
    bronze_records = datalake.load_all_bronze()
    bronze_map: dict[str, str] = {
        str(b.document.id): (b.document.uploaded_by or "")
        for b in bronze_records
    }
    owner_map: dict[str, str] = {
        str(b.document.id): (b.document.owner_id or b.document.uploaded_by or "")
        for b in bronze_records
    }
    upload_at_map: dict[str, datetime] = {
        str(b.document.id): b.document.upload_at
        for b in bronze_records
    }

    # Filtrer selon le rôle
    if is_admin:
        owned_ids = None  # accès à tout
    else:
        owned_ids = {doc_id for doc_id, owner in owner_map.items() if owner == user_id}

    gold_records = datalake.load_all_gold()
    silver_records = datalake.load_all_silver()

    processed_ids: set[str] = set()
    responses: list[DocumentResponse] = []

    for gold in gold_records:
        doc_id_str = str(gold.document_id)
        if owned_ids is not None and doc_id_str not in owned_ids:
            continue
        processed_ids.add(doc_id_str)
        responses.append(DocumentResponse(
            id=gold.document_id,
            filename=doc_id_str,
            original_filename=gold.original_filename,
            status=ProcessingStatus.CURATED,
            document_type=gold.document_type,
            upload_at=upload_at_map.get(doc_id_str, gold.curated_at),
            uploaded_by=bronze_map.get(doc_id_str),
        ))

    for silver in silver_records:
        doc_id_str = str(silver.document_id)
        if doc_id_str in processed_ids:
            continue
        if owned_ids is not None and doc_id_str not in owned_ids:
            continue
        processed_ids.add(doc_id_str)
        responses.append(DocumentResponse(
            id=silver.document_id,
            filename=doc_id_str,
            original_filename=silver.original_filename,
            status=ProcessingStatus.EXTRACTED,
            document_type=silver.document_type,
            upload_at=upload_at_map.get(doc_id_str, silver.processed_at),
            uploaded_by=bronze_map.get(doc_id_str),
        ))

    # Inclure les Bronze (encore en cours de traitement)
    for bronze in bronze_records:
        doc_id_str = str(bronze.document.id)
        if doc_id_str in processed_ids:
            continue
        if owned_ids is not None and doc_id_str not in owned_ids:
            continue
        responses.append(DocumentResponse(
            id=bronze.document.id,
            filename=bronze.document.filename,
            original_filename=bronze.document.original_filename,
            status=bronze.document.status,
            upload_at=bronze.document.upload_at,
            error_message=bronze.document.error_message,
            uploaded_by=bronze.document.uploaded_by,
        ))

    return responses



@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    payload: dict = Depends(require_auth),
) -> DocumentResponse:
    user_id: str = payload["sub"]
    user_email: str | None = payload.get("email")

    if not _is_admin(payload) and not _user_owns(document_id, user_id, user_email):
        raise HTTPException(status_code=403, detail="Accès refusé")

    gold = datalake.load_gold(document_id)
    if gold:
        return DocumentResponse(
            id=gold.document_id,
            filename=str(gold.document_id),
            original_filename=gold.original_filename,
            status=ProcessingStatus.CURATED,
            document_type=gold.document_type,
            upload_at=gold.curated_at,
        )

    silver = datalake.load_silver(document_id)
    if silver:
        return DocumentResponse(
            id=silver.document_id,
            filename=str(silver.document_id),
            original_filename=silver.original_filename,
            status=ProcessingStatus.EXTRACTED,
            document_type=silver.document_type,
            upload_at=silver.processed_at,
        )

    bronze = datalake.load_bronze(document_id)
    if bronze:
        return DocumentResponse(
            id=bronze.document.id,
            filename=bronze.document.filename,
            original_filename=bronze.document.original_filename,
            status=bronze.document.status,
            upload_at=bronze.document.upload_at,
            error_message=bronze.document.error_message,
        )

    raise HTTPException(status_code=404, detail=f"Document '{document_id}' non trouvé")


@router.get("/{document_id}/extraction")
async def get_extraction(
    document_id: uuid.UUID,
    payload: dict = Depends(require_auth),
) -> JSONResponse:
    user_id: str = payload["sub"]
    user_email: str | None = payload.get("email")

    if not _is_admin(payload) and not _user_owns(document_id, user_id, user_email):
        raise HTTPException(status_code=403, detail="Accès refusé")

    silver = datalake.load_silver(document_id)
    if not silver:
        raise HTTPException(status_code=404, detail="Extraction non disponible pour ce document")
    return JSONResponse(content=silver.extraction.model_dump(mode="json"))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    payload: dict = Depends(require_auth),
) -> None:
    user_id: str = payload["sub"]
    user_email: str | None = payload.get("email")

    if not _is_admin(payload) and not _user_owns(document_id, user_id, user_email):
        raise HTTPException(status_code=403, detail="Accès refusé")

    success = datalake.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document non trouvé ou déjà supprimé")
    curate_all_documents()
