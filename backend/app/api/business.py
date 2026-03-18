"""Routes API pour le CRM fournisseurs et le dashboard conformité."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_admin
from app.schemas.business import (
    SupplierSummary,
    build_supplier_key,
    group_type_of,
)
from app.schemas.datalake import GoldRecord
from app.schemas.fraud import AlertSeverity
from app.storage import datalake

router = APIRouter(tags=["business"])


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _match_gold_to_key(gold: GoldRecord, supplier_key: str) -> bool:
    """Retourne True si ce GoldRecord appartient à la supplier_key donnée."""
    return build_supplier_key(gold.extraction.siren, gold.extraction.emetteur_nom) == supplier_key


# ─── CRM ─────────────────────────────────────────────────────────────────────


@router.get("/api/crm/suppliers", response_model=list[SupplierSummary])
async def get_crm_suppliers(_: dict = Depends(require_admin)) -> list[SupplierSummary]:
    """
    Données CRM : fournisseurs groupés par clé composite.

    Priorité de groupement :
      1. SIREN connu  → "siren:<siren>"
      2. Nom seul     → "nom:<nom_normalisé>"
      3. Ni l'un ni l'autre → "inconnu"
    """
    gold_records = datalake.load_all_gold()
    suppliers: dict[str, dict] = {}

    for gold in gold_records:
        ext = gold.extraction
        key = build_supplier_key(ext.siren, ext.emetteur_nom)
        nom = (ext.emetteur_nom or "").strip() or "Émetteur inconnu"

        if key not in suppliers:
            suppliers[key] = {
                "supplier_key": key,
                "group_type": group_type_of(key),
                "siren": ext.siren,
                # On conserve le premier nom non-vide rencontré
                "nom": nom,
                "nombre_documents": 0,
                "total_ttc": 0.0,
                "a_des_alertes": False,
                "types_documents": set(),
            }
        else:
            # Si le nom d'affichage était générique, on le remplace
            if suppliers[key]["nom"] == "Émetteur inconnu" and nom != "Émetteur inconnu":
                suppliers[key]["nom"] = nom

        s = suppliers[key]
        s["nombre_documents"] += 1
        if ext.montants.ttc:
            s["total_ttc"] += float(ext.montants.ttc)
        if gold.alerts:
            s["a_des_alertes"] = True
        s["types_documents"].add(gold.document_type.value)

    # Tri : SIREN d'abord, puis nom, puis inconnu
    order = {"siren": 0, "nom": 1, "inconnu": 2}
    sorted_suppliers = sorted(suppliers.values(), key=lambda v: (order[v["group_type"]], v["nom"]))

    return [
        SupplierSummary(
            supplier_key=v["supplier_key"],
            group_type=v["group_type"],
            siren=v["siren"],
            nom=v["nom"],
            nombre_documents=v["nombre_documents"],
            total_ttc=round(v["total_ttc"], 2),
            a_des_alertes=v["a_des_alertes"],
            types_documents=list(v["types_documents"]),
        )
        for v in sorted_suppliers
    ]


@router.get("/api/crm/suppliers/{supplier_key:path}", response_model=list[GoldRecord])
async def get_supplier_documents(
    supplier_key: str,
    _: dict = Depends(require_admin),
) -> list[GoldRecord]:
    """
    Historique de tous les documents Gold associés à une supplier_key composite.

    La supplier_key peut être :
      - "siren:123456789"
      - "nom:acme sa"
      - "inconnu"
    """
    if not supplier_key:
        raise HTTPException(status_code=400, detail="supplier_key invalide")

    gold_records = datalake.load_all_gold()
    matched = [
        g for g in gold_records if _match_gold_to_key(g, supplier_key)
    ]

    # Tri anti-chronologique pour l'historique
    matched.sort(key=lambda g: g.curated_at, reverse=True)
    return matched


# ─── Conformité ───────────────────────────────────────────────────────────────


class ComplianceDashboard:
    pass  # Voir ci-dessous — on réutilise le modèle inline


from pydantic import BaseModel  # noqa: E402


class ComplianceDashboardSchema(BaseModel):
    total_documents: int
    documents_conformes: int
    documents_non_conformes: int
    taux_conformite: float
    alertes_critiques: int
    alertes_hautes: int
    alertes_moyennes: int
    alertes_totales: int


@router.get("/api/compliance/dashboard", response_model=ComplianceDashboardSchema)
async def get_compliance_dashboard(_: dict = Depends(require_admin)) -> ComplianceDashboardSchema:
    """Dashboard conformité : métriques globales sur l'ensemble des documents."""
    gold_records = datalake.load_all_gold()
    total = len(gold_records)
    conformes = sum(1 for g in gold_records if g.is_compliant)

    seen_ids: set[str] = set()
    critiques = hautes = moyennes = 0

    for gold in gold_records:
        for alert in gold.alerts:
            if alert.id not in seen_ids:
                seen_ids.add(alert.id)
                if alert.severity == AlertSeverity.CRITIQUE:
                    critiques += 1
                elif alert.severity == AlertSeverity.HAUTE:
                    hautes += 1
                elif alert.severity == AlertSeverity.MOYENNE:
                    moyennes += 1

    return ComplianceDashboardSchema(
        total_documents=total,
        documents_conformes=conformes,
        documents_non_conformes=total - conformes,
        taux_conformite=round(conformes / total * 100, 1) if total > 0 else 100.0,
        alertes_critiques=critiques,
        alertes_hautes=hautes,
        alertes_moyennes=moyennes,
        alertes_totales=len(seen_ids),
    )
