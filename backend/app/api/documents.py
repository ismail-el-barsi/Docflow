"""Routes API pour la gestion des documents."""
import logging
import uuid
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
ALLOWED_MIME = {"application/pdf"}


def _is_admin(payload: dict) -> bool:
    return payload.get("role") == "admin"


def _user_owns(document_id: uuid.UUID, user_id: str) -> bool:
    """Vérifie que le document appartient à l'utilisateur via le bronze record."""
    bronze = datalake.load_bronze(document_id)
    if not bronze:
        return False
    return bronze.document.uploaded_by == user_id


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_auth),
) -> list[DocumentResponse]:
    """Upload un ou plusieurs fichiers PDF et lance leur traitement en arrière-plan."""
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    responses: list[DocumentResponse] = []
    user_id: str = payload["sub"]

    for file in files:
        if file.content_type not in ALLOWED_MIME:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Type de fichier non supporté : {file.content_type}."
                    " Seuls les PDF sont acceptés."
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
            uploaded_by=user_id,
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
    try:
        process_document(document, file_path)
        curate_all_documents()
    except Exception as exc:
        logger.error("Erreur pipeline pour '%s' : %s", document.original_filename, exc)


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(payload: dict = Depends(require_auth)) -> list[DocumentResponse]:
    """Liste les documents — admin : tous, user : seulement les siens."""
    user_id: str = payload["sub"]
    is_admin = _is_admin(payload)

    gold_records = datalake.load_all_gold()
    silver_records = datalake.load_all_silver()

    # Résoudre les document_ids accessibles pour cet utilisateur
    if not is_admin:
        owned_ids = _get_owned_ids(user_id)
    else:
        owned_ids = None  # None = accès à tout

    gold_ids: set[str] = set()
    responses: list[DocumentResponse] = []

    for gold in gold_records:
        doc_id_str = str(gold.document_id)
        if owned_ids is not None and doc_id_str not in owned_ids:
            continue
        gold_ids.add(doc_id_str)
        responses.append(DocumentResponse(
            id=gold.document_id,
            filename=doc_id_str,
            original_filename=gold.original_filename,
            status=ProcessingStatus.CURATED,
            document_type=gold.document_type,
            upload_at=gold.curated_at,
        ))

    for silver in silver_records:
        doc_id_str = str(silver.document_id)
        if doc_id_str in gold_ids:
            continue
        if owned_ids is not None and doc_id_str not in owned_ids:
            continue
        responses.append(DocumentResponse(
            id=silver.document_id,
            filename=doc_id_str,
            original_filename=silver.original_filename,
            status=ProcessingStatus.EXTRACTED,
            document_type=silver.document_type,
            upload_at=silver.processed_at,
        ))

    return responses


def _get_owned_ids(user_id: str) -> set[str]:
    """Retourne les document_ids appartenant à cet user (via bronze records)."""
    owned: set[str] = set()
    bronze_dir = Path("./storage/bronze")
    if not bronze_dir.exists():
        return owned
    for p in bronze_dir.glob("*.json"):
        try:
            record = datalake.load_bronze_from_path(p)
            if record and record.document.uploaded_by == user_id:
                owned.add(str(record.document.id))
        except Exception:
            continue
    return owned


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    payload: dict = Depends(require_auth),
) -> DocumentResponse:
    user_id: str = payload["sub"]

    if not _is_admin(payload) and not _user_owns(document_id, user_id):
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
            status=ProcessingStatus.UPLOADED,
            upload_at=bronze.document.upload_at,
        )

    raise HTTPException(status_code=404, detail=f"Document '{document_id}' non trouvé")


@router.get("/{document_id}/extraction")
async def get_extraction(
    document_id: uuid.UUID,
    payload: dict = Depends(require_auth),
) -> JSONResponse:
    user_id: str = payload["sub"]

    if not _is_admin(payload) and not _user_owns(document_id, user_id):
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

    if not _is_admin(payload) and not _user_owns(document_id, user_id):
        raise HTTPException(status_code=403, detail="Accès refusé")

    success = datalake.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document non trouvé ou déjà supprimé")
    curate_all_documents()
