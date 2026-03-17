"""Service de gestion du Data Lake Medallion (Bronze → Silver → Gold)."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.schemas.datalake import BronzeRecord, DataLakeManifest, GoldRecord, SilverRecord
from app.schemas.document import ProcessingStatus, UploadedDocument
from app.db.mongodb import get_collection

logger = logging.getLogger(__name__)


def _get_base_path() -> Path:
    base = os.getenv("STORAGE_BASE_PATH", "./storage")
    return Path(base)


def _zone_path(zone: str) -> Path:
    path = _get_base_path() / zone
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(zone: str) -> Path:
    return _zone_path(zone) / "manifest.json"


def _load_manifest(zone: str) -> DataLakeManifest:
    path = _manifest_path(zone)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return DataLakeManifest(**data)
    return DataLakeManifest(zone=zone)


def _save_manifest(manifest: DataLakeManifest) -> None:
    manifest.last_updated = datetime.utcnow()
    path = _manifest_path(manifest.zone)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


# ─── Bronze ──────────────────────────────────────────────────────────────────

def save_bronze(document: UploadedDocument, file_bytes: bytes) -> BronzeRecord:
    """Sauvegarde le fichier brut dans la zone Bronze."""
    zone = _zone_path("bronze")
    file_path = zone / document.filename
    file_path.write_bytes(file_bytes)

    record = BronzeRecord(document=document, file_path=str(file_path))
    record_path = zone / f"{document.id}.json"
    record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    manifest = _load_manifest("bronze")
    if str(document.id) not in manifest.records:
        manifest.records.append(str(document.id))
    _save_manifest(manifest)

    # Sauvegarde MongoDB
    try:
        get_collection("bronze").replace_one(
            {"document.id": str(document.id)},
            record.model_dump(mode="json"),
            upsert=True
        )
    except Exception as exc:
        logger.warning("Erreur sauvegarde MongoDB (Bronze) : %s", exc)

    logger.info("Bronze : document '%s' sauvegardé → %s", document.original_filename, file_path)
    return record


def update_bronze_status(document_id: UUID, status: ProcessingStatus, error_message: str | None = None) -> None:
    """Met à jour le statut du document dans son record Bronze."""
    record = load_bronze(document_id)
    if record:
        record.document.status = status
        record.document.error_message = error_message
        zone = _zone_path("bronze")
        record_path = zone / f"{document_id}.json"
        record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        # Mise à jour MongoDB
        try:
            get_collection("bronze").update_one(
                {"document.id": str(document_id)},
                {"$set": {"document.status": status.value, "document.error_message": error_message}}
            )
        except Exception as exc:
            logger.warning("Erreur mise à jour MongoDB (Bronze) : %s", exc)


def load_bronze(document_id: UUID) -> BronzeRecord | None:
    # Priorité MongoDB
    try:
        data = get_collection("bronze").find_one({"document.id": str(document_id)})
        if data:
            return BronzeRecord(**data)
    except Exception as exc:
        logger.debug("MongoDB indisponible pour load_bronze: %s", exc)

    # Fallback FileSystem
    zone = _zone_path("bronze")
    record_path = zone / f"{document_id}.json"
    if not record_path.exists():
        return None
    data = json.loads(record_path.read_text(encoding="utf-8"))
    return BronzeRecord(**data)


def load_all_bronze() -> list[BronzeRecord]:
    """Charge tous les enregistrements Bronze."""
    # Priorité MongoDB
    try:
        cursor = get_collection("bronze").find()
        return [BronzeRecord(**data) for data in cursor]
    except Exception as exc:
        logger.warning("MongoDB indisponible pour load_all_bronze : %s", exc)

    # Fallback FileSystem
    zone = _zone_path("bronze")
    records = []
    for path in zone.glob("*.json"):
        if path.name == "manifest.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append(BronzeRecord(**data))
        except Exception as exc:
            logger.warning("Erreur chargement bronze '%s' : %s", path.name, exc)
    return records


# ─── Silver ──────────────────────────────────────────────────────────────────

def save_silver(record: SilverRecord) -> None:
    """Sauvegarde les données extraites dans la zone Silver."""
    zone = _zone_path("silver")
    record_path = zone / f"{record.document_id}.json"
    record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    manifest = _load_manifest("silver")
    if str(record.document_id) not in manifest.records:
        manifest.records.append(str(record.document_id))
    _save_manifest(manifest)

    # Sauvegarde MongoDB
    try:
        get_collection("silver").replace_one(
            {"document_id": str(record.document_id)},
            record.model_dump(mode="json"),
            upsert=True
        )
    except Exception as exc:
        logger.warning("Erreur sauvegarde MongoDB (Silver) : %s", exc)

    logger.info("Silver : document '%s' extrait", record.original_filename)


def load_silver(document_id: UUID) -> SilverRecord | None:
    # Priorité MongoDB
    try:
        data = get_collection("silver").find_one({"document_id": str(document_id)})
        if data:
            return SilverRecord(**data)
    except Exception as exc:
        logger.debug("MongoDB indisponible pour load_silver: %s", exc)

    # Fallback FileSystem
    zone = _zone_path("silver")
    record_path = zone / f"{document_id}.json"
    if not record_path.exists():
        return None
    data = json.loads(record_path.read_text(encoding="utf-8"))
    return SilverRecord(**data)


def load_all_silver() -> list[SilverRecord]:
    """Charge tous les enregistrements Silver (pour l'analyse cross-documents)."""
    # Priorité MongoDB
    try:
        cursor = get_collection("silver").find()
        return [SilverRecord(**data) for data in cursor]
    except Exception as exc:
        logger.warning("MongoDB indisponible pour load_all_silver : %s", exc)

    # Fallback FileSystem
    zone = _zone_path("silver")
    records = []
    for path in zone.glob("*.json"):
        if path.name == "manifest.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append(SilverRecord(**data))
        except Exception as exc:
            logger.warning("Erreur chargement silver '%s' : %s", path.name, exc)
    return records


# ─── Gold ────────────────────────────────────────────────────────────────────

def save_gold(record: GoldRecord) -> None:
    """Sauvegarde les données curées dans la zone Gold."""
    zone = _zone_path("gold")
    record_path = zone / f"{record.document_id}.json"
    record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    manifest = _load_manifest("gold")
    if str(record.document_id) not in manifest.records:
        manifest.records.append(str(record.document_id))
    _save_manifest(manifest)

    # Sauvegarde MongoDB
    try:
        get_collection("gold").replace_one(
            {"document_id": str(record.document_id)},
            record.model_dump(mode="json"),
            upsert=True
        )
    except Exception as exc:
        logger.warning("Erreur sauvegarde MongoDB (Gold) : %s", exc)

    logger.info(
        "Gold : document '%s' curé (%d alertes, conforme=%s)",
        record.original_filename,
        len(record.alerts),
        record.is_compliant,
    )


def load_gold(document_id: UUID) -> GoldRecord | None:
    # Priorité MongoDB
    try:
        data = get_collection("gold").find_one({"document_id": str(document_id)})
        if data:
            return GoldRecord(**data)
    except Exception as exc:
        logger.debug("MongoDB indisponible pour load_gold: %s", exc)

    # Fallback FileSystem
    zone = _zone_path("gold")
    record_path = zone / f"{document_id}.json"
    if not record_path.exists():
        return None
    data = json.loads(record_path.read_text(encoding="utf-8"))
    return GoldRecord(**data)


def load_all_gold() -> list[GoldRecord]:
    """Charge tous les enregistrements Gold."""
    # Priorité MongoDB
    try:
        cursor = get_collection("gold").find()
        return [GoldRecord(**data) for data in cursor]
    except Exception as exc:
        logger.warning("MongoDB indisponible pour load_all_gold : %s", exc)

    # Fallback FileSystem
    zone = _zone_path("gold")
    records = []
    for path in zone.glob("*.json"):
        if path.name == "manifest.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append(GoldRecord(**data))
        except Exception as exc:
            logger.warning("Erreur chargement gold '%s' : %s", path.name, exc)
    return records


# ─── Suppression ─────────────────────────────────────────────────────────────

def delete_document(document_id: UUID) -> bool:
    """Supprime un document à tous les niveaux du Data Lake."""
    success = False
    doc_id_str = str(document_id)

    # 1. Bronze : Supprimer le PDF et le JSON
    bronze = load_bronze(document_id)
    if bronze:
        pdf_path = Path(bronze.file_path)
        if pdf_path.exists():
            pdf_path.unlink()
        
        record_path = _zone_path("bronze") / f"{doc_id_str}.json"
        if record_path.exists():
            record_path.unlink()
        
        _remove_from_manifest("bronze", doc_id_str)
        success = True

    # 2. Silver : Supprimer le JSON
    silver_path = _zone_path("silver") / f"{doc_id_str}.json"
    if silver_path.exists():
        silver_path.unlink()
        _remove_from_manifest("silver", doc_id_str)
        success = True

    # 3. Gold : Supprimer le JSON
    gold_path = _zone_path("gold") / f"{doc_id_str}.json"
    if gold_path.exists():
        gold_path.unlink()
        _remove_from_manifest("gold", doc_id_str)
        success = True

    # 4. MongoDB : Supprimer des 3 zones
    try:
        get_collection("bronze").delete_one({"document.id": doc_id_str})
        get_collection("silver").delete_one({"document_id": doc_id_str})
        get_collection("gold").delete_one({"document_id": doc_id_str})
    except Exception as exc:
        logger.warning("Erreur suppression MongoDB pour '%s' : %s", doc_id_str, exc)

    if success:
        logger.info("Document '%s' supprimé de toutes les zones", doc_id_str)
    
    return success


def _remove_from_manifest(zone: str, document_id: str) -> None:
    manifest = _load_manifest(zone)
    if document_id in manifest.records:
        manifest.records.remove(document_id)
        _save_manifest(manifest)
