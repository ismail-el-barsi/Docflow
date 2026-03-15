"""Tests TDD pour les schemas Pydantic — Phase 2."""
import pytest
from pydantic import ValidationError

from app.schemas.classification import ClassificationResult
from app.schemas.document import DocumentType, ProcessingStatus
from app.schemas.extraction import ExtractedData, MonetaryAmount
from app.schemas.fraud import AlertSeverity, AlertType, InconsistencyAlert

# ─── DocumentType ────────────────────────────────────────────────────────────

def test_document_type_values():
    assert DocumentType.FACTURE == "facture"
    assert DocumentType.DEVIS == "devis"
    assert DocumentType.ATTESTATION == "attestation"
    assert DocumentType.AUTRE == "autre"


def test_processing_status_progression():
    statuses = list(ProcessingStatus)
    assert ProcessingStatus.UPLOADED in statuses
    assert ProcessingStatus.CURATED in statuses


# ─── ExtractedData ───────────────────────────────────────────────────────────

def test_siren_valid():
    data = ExtractedData(siren="123456789", raw_text="test")
    assert data.siren == "123456789"


def test_siren_invalid_raises():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedData(siren="12345", raw_text="test")
    assert "SIREN invalide" in str(exc_info.value)


def test_siren_non_numeric_raises():
    with pytest.raises(ValidationError):
        ExtractedData(siren="12345678A", raw_text="test")


def test_siret_valid():
    data = ExtractedData(siret="12345678901234", raw_text="test")
    assert data.siret == "12345678901234"


def test_siret_invalid_raises():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedData(siret="1234567890", raw_text="test")
    assert "SIRET invalide" in str(exc_info.value)


def test_monetary_amount_defaults():
    amount = MonetaryAmount()
    assert amount.currency == "EUR"
    assert amount.ht is None
    assert amount.ttc is None


def test_extracted_data_all_none_fields_allowed():
    """Tous les champs sauf raw_text sont optionnels."""
    data = ExtractedData(raw_text="Aucune donnée extraite")
    assert data.siren is None
    assert data.siret is None
    assert data.emetteur_nom is None


# ─── ClassificationResult ────────────────────────────────────────────────────

def test_classification_confidence_bounds():
    result = ClassificationResult(
        document_type=DocumentType.FACTURE,
        confidence=0.95,
        model_used="gpt-oss:20b"
    )
    assert result.confidence == 0.95


def test_classification_confidence_out_of_bounds():
    with pytest.raises(ValidationError):
        ClassificationResult(
            document_type=DocumentType.FACTURE,
            confidence=1.5,
            model_used="gpt-oss:20b"
        )


# ─── InconsistencyAlert ──────────────────────────────────────────────────────

def test_alert_siret_mismatch():
    alert = InconsistencyAlert(
        id="alert-001",
        alert_type=AlertType.SIRET_MISMATCH,
        severity=AlertSeverity.CRITIQUE,
        description="SIRET différent entre attestation et facture",
        field_in_conflict="siret",
        value_a="12345678901234",
        value_b="98765432109876",
    )
    assert alert.severity == AlertSeverity.CRITIQUE
    assert alert.alert_type == AlertType.SIRET_MISMATCH
