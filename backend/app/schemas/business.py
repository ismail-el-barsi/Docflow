"""Schémas Pydantic pour le CRM fournisseurs — groupement composite."""
from typing import Literal

from pydantic import BaseModel

# ─── Clé de groupement ───────────────────────────────────────────────────────

GroupType = Literal["siren", "nom", "inconnu"]

UNKNOWN_KEY = "inconnu"
SIREN_PREFIX = "siren:"
NOM_PREFIX = "nom:"


def build_supplier_key(siren: str | None, emetteur_nom: str | None) -> str:
    """
    Calcule la clé composite de groupement :
      • SIREN connu    → "siren:123456789"
      • Nom seul       → "nom:acme_sa"   (normalisé lower-ascii-like)
      • Ni l'un ni l'autre → "inconnu"
    """
    if siren:
        return f"{SIREN_PREFIX}{siren}"
    nom = (emetteur_nom or "").strip()
    if nom:
        return f"{NOM_PREFIX}{nom.lower()}"
    return UNKNOWN_KEY


def group_type_of(supplier_key: str) -> GroupType:
    if supplier_key.startswith(SIREN_PREFIX):
        return "siren"
    if supplier_key.startswith(NOM_PREFIX):
        return "nom"
    return "inconnu"


# ─── Schémas API ─────────────────────────────────────────────────────────────


class SupplierSummary(BaseModel):
    """Résumé d'un fournisseur (carte CRM)."""

    supplier_key: str
    """Identifiant opaque utilisé comme paramètre de route."""

    group_type: GroupType
    """Type de groupement utilisé pour former ce fournisseur."""

    siren: str | None
    """SIREN si connu, None sinon."""

    nom: str
    """Nom d'affichage (émetteur ou 'Émetteur inconnu')."""

    nombre_documents: int
    total_ttc: float
    a_des_alertes: bool
    types_documents: list[str]
