"""Routes API pour le CRM fournisseurs et le dashboard conformité."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_admin

from app.schemas.datalake import GoldRecord
from app.schemas.fraud import AlertSeverity
from app.storage import datalake

router = APIRouter(tags=["business"])


# ─── CRM ─────────────────────────────────────────────────────────────────────

class SupplierSummary(BaseModel):
    siren: str
    nom: str
    nombre_documents: int
    total_ttc: float
    a_des_alertes: bool
    types_documents: list[str]


@router.get("/api/crm/suppliers", response_model=list[SupplierSummary])
async def get_crm_suppliers(_: dict = Depends(require_admin)) -> list[SupplierSummary]:
    """Données CRM : fournisseurs groupés par SIREN avec montants cumulés."""
    gold_records = datalake.load_all_gold()
    suppliers: dict[str, dict] = {}

    for gold in gold_records:
        ext = gold.extraction
        siren = ext.siren or "INCONNU"
        nom = ext.emetteur_nom or "Émetteur inconnu"

        if siren not in suppliers:
            suppliers[siren] = {
                "siren": siren,
                "nom": nom,
                "nombre_documents": 0,
                "total_ttc": 0.0,
                "a_des_alertes": False,
                "types_documents": set(),
            }

        s = suppliers[siren]
        s["nombre_documents"] += 1
        if ext.montants.ttc:
            s["total_ttc"] += float(ext.montants.ttc)
        if gold.alerts:
            s["a_des_alertes"] = True
        s["types_documents"].add(gold.document_type.value)

    return [
        SupplierSummary(
            siren=v["siren"],
            nom=v["nom"],
            nombre_documents=v["nombre_documents"],
            total_ttc=round(v["total_ttc"], 2),
            a_des_alertes=v["a_des_alertes"],
            types_documents=list(v["types_documents"]),
        )
        for v in suppliers.values()
    ]


@router.get("/api/crm/suppliers/{siren}", response_model=list[GoldRecord])
async def get_supplier_documents(siren: str, _: dict = Depends(require_admin)) -> list[GoldRecord]:
    """Récupère tous les documents Gold associés à un SIREN spécifique."""
    gold_records = datalake.load_all_gold()
    return [g for g in gold_records if g.extraction.siren == siren]


# ─── Conformité ───────────────────────────────────────────────────────────────

class ComplianceDashboard(BaseModel):
    total_documents: int
    documents_conformes: int
    documents_non_conformes: int
    taux_conformite: float
    alertes_critiques: int
    alertes_hautes: int
    alertes_moyennes: int
    alertes_totales: int


@router.get("/api/compliance/dashboard", response_model=ComplianceDashboard)
async def get_compliance_dashboard(_: dict = Depends(require_admin)) -> ComplianceDashboard:
    """Dashboard conformité : métriques globales sur l'ensemble des documents."""
    gold_records = datalake.load_all_gold()
    total = len(gold_records)
    conformes = sum(1 for g in gold_records if g.is_compliant)

    # Déduplique les alertes
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

    return ComplianceDashboard(
        total_documents=total,
        documents_conformes=conformes,
        documents_non_conformes=total - conformes,
        taux_conformite=round(conformes / total * 100, 1) if total > 0 else 100.0,
        alertes_critiques=critiques,
        alertes_hautes=hautes,
        alertes_moyennes=moyennes,
        alertes_totales=len(seen_ids),
    )
