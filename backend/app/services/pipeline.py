"""Pipeline de traitement d'un document : OCR → Classification → Extraction → Data Lake."""

import logging
from pathlib import Path

from app.schemas.classification import ClassificationResult
from app.schemas.datalake import GoldRecord, SilverRecord
from app.schemas.document import UploadedDocument
from app.schemas.fraud import InconsistencyAlert
from app.services import classifier, extractor
from app.services.fraud import detect_inconsistencies
from app.services.ocr import extract_text_from_pdf_path
from app.storage import datalake

logger = logging.getLogger(__name__)


def process_document(document: UploadedDocument, file_path: Path) -> SilverRecord:
    """
    Lance le pipeline complet OCR → Classification → Extraction → Silver.
    Retourne le SilverRecord produit.
    """
    # OCR
    logger.info("Démarrage OCR : %s", document.original_filename)
    ocr_result = extract_text_from_pdf_path(file_path)

    if not ocr_result.success:
        logger.error("Échec OCR pour %s : %s", document.original_filename, ocr_result.error)
        # On continue avec un texte vide (le LLM risque de ne rien extraire)

    # Classification
    logger.info("Classification LLM : %s", document.original_filename)
    classification: ClassificationResult = classifier.classify_document(ocr_result.text)

    # Extraction
    logger.info("Extraction LLM : %s", document.original_filename)
    extracted = extractor.extract_document_data(ocr_result.text)

    # Sauvegarde Silver
    silver = SilverRecord(
        document_id=document.id,
        original_filename=document.original_filename,
        document_type=classification.document_type,
        classification=classification,
        extraction=extracted,
    )
    datalake.save_silver(silver)
    return silver


def curate_all_documents() -> list[InconsistencyAlert]:
    """
    Charge tous les Silver, lance la détection d'incohérences,
    puis sauvegarde chaque GoldRecord.
    Retourne la liste complète des alertes trouvées.
    """
    all_silver = datalake.load_all_silver()
    if not all_silver:
        return []

    alerts = detect_inconsistencies(all_silver)
    # Index des alertes par document
    alerts_by_doc: dict[str, list[InconsistencyAlert]] = {}
    for alert in alerts:
        for doc_id in alert.document_ids:
            alerts_by_doc.setdefault(str(doc_id), []).append(alert)

    for silver in all_silver:
        doc_alerts = alerts_by_doc.get(str(silver.document_id), [])
        gold = GoldRecord(
            document_id=silver.document_id,
            original_filename=silver.original_filename,
            document_type=silver.document_type,
            extraction=silver.extraction,
            alerts=doc_alerts,
            is_compliant=len(doc_alerts) == 0,
        )
        datalake.save_gold(gold)

    logger.info("Curation terminée : %d docs, %d alertes", len(all_silver), len(alerts))
    return alerts
