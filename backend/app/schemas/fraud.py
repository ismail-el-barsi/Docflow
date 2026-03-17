from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AlertType(StrEnum):
    SIRET_MISMATCH = "siret_mismatch"
    AMOUNT_INCONSISTENCY = "amount_inconsistency"
    DATE_INCOHERENCE = "date_incoherence"
    SIREN_FORMAT_INVALID = "siren_format_invalid"
    SIREN_NOT_FOUND = "siren_not_found"
    SIREN_COMPANY_CLOSED = "siren_company_closed"
    SIRET_NOT_FOUND = "siret_not_found"
    SIRET_CLOSED = "siret_closed"
    COMPANY_NAME_MISMATCH = "company_name_mismatch"
    COMPANY_ADDRESS_MISMATCH = "company_address_mismatch"


class AlertSeverity(StrEnum):
    CRITIQUE = "critique"
    HAUTE = "haute"
    MOYENNE = "moyenne"
    FAIBLE = "faible"


class InconsistencyAlert(BaseModel):
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    description: str
    document_ids: list[UUID] = Field(default_factory=list)
    field_in_conflict: str | None = None
    value_a: str | None = None
    value_b: str | None = None
    suggestion: str | None = None
