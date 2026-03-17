"""Routes API pour les alertes de fraude (zone Gold)."""

from fastapi import APIRouter, Depends

from app.api.auth import require_admin
from app.schemas.fraud import AlertSeverity, AlertType, InconsistencyAlert
from app.storage import datalake

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/", response_model=list[InconsistencyAlert])
async def list_alerts(
    severity: AlertSeverity | None = None,
    alert_type: AlertType | None = None,
    _: dict = Depends(require_admin),
) -> list[InconsistencyAlert]:
    """Liste toutes les alertes de fraude/incohérence, avec filtres optionnels."""
    gold_records = datalake.load_all_gold()
    seen_ids: set[str] = set()
    all_alerts: list[InconsistencyAlert] = []

    for gold in gold_records:
        for alert in gold.alerts:
            if alert.id not in seen_ids:
                seen_ids.add(alert.id)
                all_alerts.append(alert)

    # Filtres
    if severity:
        all_alerts = [a for a in all_alerts if a.severity == severity]
    if alert_type:
        all_alerts = [a for a in all_alerts if a.alert_type == alert_type]

    # Tri par sévérité décroissante
    severity_order = {
        AlertSeverity.CRITIQUE: 0,
        AlertSeverity.HAUTE: 1,
        AlertSeverity.MOYENNE: 2,
        AlertSeverity.FAIBLE: 3,
    }
    all_alerts.sort(key=lambda a: severity_order.get(a.severity, 99))
    return all_alerts
