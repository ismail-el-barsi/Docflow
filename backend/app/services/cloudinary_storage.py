"""Helpers Cloudinary pour stocker les documents uploades."""

import logging
import os
from pathlib import Path
from typing import NamedTuple
from uuid import UUID

import cloudinary
import cloudinary.exceptions
import cloudinary.uploader

logger = logging.getLogger(__name__)
_CONFIGURED = False


class CloudinaryUploadResult(NamedTuple):
    url: str
    public_id: str


def is_cloudinary_configured() -> bool:
    """Indique si la configuration minimale Cloudinary est presente."""
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def _resource_type_for_mime(mime_type: str) -> str:
    normalized_mime = mime_type.lower().strip()
    if normalized_mime == "application/pdf":
        return "raw"
    if normalized_mime.startswith("image/"):
        return "image"
    return "auto"


def _public_id_for_upload(document_id: UUID, original_filename: str, mime_type: str) -> str:
    normalized_mime = mime_type.lower().strip()
    if normalized_mime == "application/pdf":
        extension = Path(original_filename).suffix.lower()
        if extension != ".pdf":
            extension = ".pdf"
        return f"{document_id}{extension}"
    return str(document_id)


def _ensure_configured() -> str:
    """Configure le SDK Cloudinary a partir des variables d'environnement."""
    global _CONFIGURED

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    folder = os.getenv("CLOUDINARY_FOLDER", "docflow")

    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError(
            "Configuration Cloudinary manquante "
            "(CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET)"
        )

    if not _CONFIGURED:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        _CONFIGURED = True

    return folder


def upload_document_bytes(
    file_bytes: bytes,
    *,
    document_id: UUID,
    original_filename: str,
    mime_type: str,
) -> CloudinaryUploadResult:
    """Upload un document (PDF ou image) sur Cloudinary."""
    folder = _ensure_configured()
    resource_type = _resource_type_for_mime(mime_type)
    public_id = _public_id_for_upload(document_id, original_filename, mime_type)

    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            resource_type=resource_type,
            folder=folder,
            public_id=public_id,
            overwrite=True,
            unique_filename=False,
            use_filename=False,
            tags=["docflow", mime_type],
        )
    except cloudinary.exceptions.Error as exc:
        raise RuntimeError(f"Echec upload Cloudinary: {exc}") from exc

    secure_url = str(result.get("secure_url") or "")
    public_id = str(result.get("public_id") or "")

    if not secure_url or not public_id:
        raise RuntimeError("Cloudinary n'a pas renvoye secure_url/public_id")

    return CloudinaryUploadResult(url=secure_url, public_id=public_id)


def delete_document(public_id: str) -> None:
    """Supprime un document Cloudinary (image ou raw)."""
    if not public_id:
        return

    if not is_cloudinary_configured():
        return

    _ensure_configured()

    for resource_type in ("raw", "image"):
        try:
            cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type,
                invalidate=True,
            )
        except cloudinary.exceptions.Error as exc:
            logger.warning(
                "Suppression Cloudinary echouee pour %s (resource_type=%s): %s",
                public_id,
                resource_type,
                exc,
            )
