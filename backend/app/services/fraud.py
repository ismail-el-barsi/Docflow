"""Service de détection d'incohérences et fraudes inter-documents."""
import logging
import os
import re
import unicodedata
import uuid
from decimal import Decimal

import httpx
from app.schemas.datalake import SilverRecord
from app.schemas.document import DocumentType
from app.schemas.fraud import AlertSeverity, AlertType, InconsistencyAlert

logger = logging.getLogger(__name__)

# Tolérance pour la comparaison de montants (5%)
AMOUNT_TOLERANCE_RATIO = Decimal("0.05")


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = without_accents.lower()
    compact = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", compact).strip()


def _build_official_address(adresse_etab: dict) -> str:
    voie = " ".join(
        str(part).strip()
        for part in [
            adresse_etab.get("numeroVoieEtablissement"),
            adresse_etab.get("typeVoieEtablissement"),
            adresse_etab.get("libelleVoieEtablissement"),
        ]
        if part
    ).strip()
    locality = " ".join(
        str(part).strip()
        for part in [
            adresse_etab.get("codePostalEtablissement"),
            adresse_etab.get("libelleCommuneEtablissement"),
        ]
        if part
    ).strip()
    return " ".join(part for part in [voie, locality] if part).strip()


def _extract_legal_info(unite_legale: dict) -> tuple[str | None, str | None]:
    if not unite_legale:
        return None, None

    periodes_ul = unite_legale.get("periodesUniteLegale", [])
    latest = periodes_ul[0] if periodes_ul else {}

    etat = latest.get("etatAdministratifUniteLegale") or unite_legale.get("etatAdministratifUniteLegale")
    denomination = (
        latest.get("denominationUniteLegale")
        or latest.get("nomUniteLegale")
        or unite_legale.get("denominationUniteLegale")
        or unite_legale.get("nomUniteLegale")
    )
    return etat, denomination


def _is_address_mismatch(extracted_address: str | None, adresse_etab: dict) -> bool:
    if not extracted_address or not adresse_etab:
        return False

    extracted_norm = _normalize_text(extracted_address)
    if not extracted_norm:
        return False

    official_city = _normalize_text(adresse_etab.get("libelleCommuneEtablissement"))
    official_postal = (adresse_etab.get("codePostalEtablissement") or "").strip()
    official_street = _normalize_text(
        " ".join(
            str(part).strip()
            for part in [
                adresse_etab.get("numeroVoieEtablissement"),
                adresse_etab.get("typeVoieEtablissement"),
                adresse_etab.get("libelleVoieEtablissement"),
            ]
            if part
        )
    )

    ext_postal_match = re.search(r"\b\d{5}\b", extracted_address)
    ext_postal = ext_postal_match.group(0) if ext_postal_match else None
    postal_mismatch = bool(official_postal and ext_postal and official_postal != ext_postal)

    city_mismatch = bool(official_city and official_city not in extracted_norm)

    street_tokens = [tok for tok in official_street.split() if len(tok) > 2 and not tok.isdigit()]
    street_overlap = sum(1 for tok in street_tokens if tok in extracted_norm)
    street_mismatch = bool(street_tokens and street_overlap == 0)

    return postal_mismatch or city_mismatch or street_mismatch


def _extract_declared_siren(raw_text: str | None) -> tuple[str | None, str | None]:
    """Extrait la valeur SIREN déclarée dans le texte OCR brut."""
    if not raw_text:
        return None, None

    for line in raw_text.splitlines():
        if not re.search(r"\bsiren\b", line, flags=re.IGNORECASE):
            continue

        candidate = re.sub(
            r"^.*?\bsiren\b\s*[:=]?\s*",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip()
        candidate = re.split(
            r"\b(siret|montant|tva|ttc|date|facture|devis)\b",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" -\t")

        digits = re.sub(r"\D", "", candidate)
        if digits:
            return digits, candidate

    return None, None


def detect_inconsistencies(records: list[SilverRecord]) -> list[InconsistencyAlert]:
    """
    Analyse un ensemble de SilverRecords et retourne toutes les alertes détectées.
    Les règles s'appliquent sur l'ensemble du batch de documents.
    """
    alerts: list[InconsistencyAlert] = []

    alerts.extend(_check_siren_format(records))
    alerts.extend(_check_siret_mismatch(records))
    alerts.extend(_check_amount_inconsistency(records))
    alerts.extend(_check_date_incoherence(records))
    alerts.extend(_check_insee_registry(records))

    logger.info("%d alertes détectées sur %d documents", len(alerts), len(records))
    return alerts


# ─── Règle 1 : Format SIREN invalide ──────────────────────────────────────────

def _check_siren_format(records: list[SilverRecord]) -> list[InconsistencyAlert]:
    alerts = []
    for rec in records:
        ext = rec.extraction

        if ext.siren is not None:
            clean_siren = re.sub(r"\D", "", ext.siren)
            if not re.fullmatch(r"\d{9}", clean_siren):
                alerts.append(InconsistencyAlert(
                    id=str(uuid.uuid4()),
                    alert_type=AlertType.SIREN_FORMAT_INVALID,
                    severity=AlertSeverity.HAUTE,
                    description=f"SIREN '{clean_siren}' invalide dans '{rec.original_filename}'",
                    document_ids=[rec.document_id],
                    field_in_conflict="siren",
                    value_a=clean_siren,
                    suggestion="Vérifier le numéro SIREN du document source.",
                ))
            continue

        raw_siren_digits, raw_siren_value = _extract_declared_siren(ext.raw_text)
        if raw_siren_digits and not re.fullmatch(r"\d{9}", raw_siren_digits):
            logger.warning(
                "SIREN brut invalide détecté dans %s : %s",
                rec.original_filename,
                raw_siren_value,
            )
            alerts.append(InconsistencyAlert(
                id=str(uuid.uuid4()),
                alert_type=AlertType.SIREN_FORMAT_INVALID,
                severity=AlertSeverity.HAUTE,
                description=(
                    f"SIREN '{raw_siren_value}' invalide dans '{rec.original_filename}'"
                ),
                document_ids=[rec.document_id],
                field_in_conflict="siren",
                value_a=raw_siren_value,
                suggestion="Vérifier le numéro SIREN du document source.",
            ))
    return alerts


# ─── Règle 2 : SIRET incohérent entre documents ───────────────────────────────

def _check_siret_mismatch(records: list[SilverRecord]) -> list[InconsistencyAlert]:
    """Détecte si deux documents avec le même émetteur ont des SIRET différents."""
    alerts = []
    # Grouper par nom d'émetteur (normalisé)
    by_emetteur: dict[str, list[SilverRecord]] = {}
    for rec in records:
        nom = (rec.extraction.emetteur_nom or "").strip().lower()
        if nom:
            by_emetteur.setdefault(nom, []).append(rec)

    for emetteur, group in by_emetteur.items():
        sirets = {
            rec.document_id: rec.extraction.siret
            for rec in group
            if rec.extraction.siret
        }
        unique_sirets = set(sirets.values())
        if len(unique_sirets) > 1:
            doc_ids = list(sirets.keys())
            siret_vals = list(unique_sirets)
            alerts.append(InconsistencyAlert(
                id=str(uuid.uuid4()),
                alert_type=AlertType.SIRET_MISMATCH,
                severity=AlertSeverity.CRITIQUE,
                description=(
                    f"SIRET incohérent pour l'émetteur '{emetteur}' : "
                    f"{siret_vals[0]} vs {siret_vals[1]}"
                ),
                document_ids=doc_ids,
                field_in_conflict="siret",
                value_a=siret_vals[0],
                value_b=siret_vals[1],
                suggestion="Vérifier l'identité légale de l'émetteur auprès du registre SIRENE.",
            ))
    return alerts


# ─── Règle 3 : Incohérence montant devis vs facture ──────────────────────────

def _check_amount_inconsistency(records: list[SilverRecord]) -> list[InconsistencyAlert]:
    """Compare les montants TTC entre devis et factures du même émetteur."""
    alerts = []
    devis = [r for r in records if r.document_type == DocumentType.DEVIS]
    factures = [r for r in records if r.document_type == DocumentType.FACTURE]

    for d in devis:
        if not d.extraction.montants.ttc:
            continue
        emetteur_d = (d.extraction.emetteur_nom or "").strip().lower()

        for f in factures:
            if not f.extraction.montants.ttc:
                continue
            emetteur_f = (f.extraction.emetteur_nom or "").strip().lower()

            if emetteur_d and emetteur_d == emetteur_f:
                ttc_devis = d.extraction.montants.ttc
                ttc_facture = f.extraction.montants.ttc
                diff = abs(ttc_devis - ttc_facture)
                tolerance = ttc_devis * AMOUNT_TOLERANCE_RATIO

                if diff > tolerance:
                    alerts.append(InconsistencyAlert(
                        id=str(uuid.uuid4()),
                        alert_type=AlertType.AMOUNT_INCONSISTENCY,
                        severity=AlertSeverity.HAUTE,
                        description=(
                            f"Montant TTC du devis ({ttc_devis} €) diffère de "
                            f"la facture ({ttc_facture} €) pour '{emetteur_d}' "
                            f"(écart de {diff:.2f} €)"
                        ),
                        document_ids=[d.document_id, f.document_id],
                        field_in_conflict="montants.ttc",
                        value_a=str(ttc_devis),
                        value_b=str(ttc_facture),
                        suggestion=(
                            "Vérifier si un avenant ou modification de commande"
                            " justifie cet écart."
                        ),
                    ))
    return alerts


# ─── Règle 4 : Incohérence de dates ──────────────────────────────────────────

def _check_date_incoherence(records: list[SilverRecord]) -> list[InconsistencyAlert]:
    """Détecte une facture avec une date antérieure au devis du même émetteur."""
    alerts = []
    devis = [
        r for r in records
        if r.document_type == DocumentType.DEVIS and r.extraction.date_emission
    ]
    factures = [
        r for r in records
        if r.document_type == DocumentType.FACTURE and r.extraction.date_emission
    ]

    for d in devis:
        emetteur_d = (d.extraction.emetteur_nom or "").strip().lower()
        date_devis = d.extraction.date_emission

        for f in factures:
            emetteur_f = (f.extraction.emetteur_nom or "").strip().lower()
            date_facture = f.extraction.date_emission

            if emetteur_d and emetteur_d == emetteur_f:
                if date_facture and date_devis and date_facture < date_devis:
                    alerts.append(InconsistencyAlert(
                        id=str(uuid.uuid4()),
                        alert_type=AlertType.DATE_INCOHERENCE,
                        severity=AlertSeverity.MOYENNE,
                        description=(
                            f"La facture ('{date_facture}') est antérieure"
                            f" au devis ('{date_devis}')"
                            f" pour l'émetteur '{emetteur_d}'"
                        ),
                        document_ids=[d.document_id, f.document_id],
                        field_in_conflict="date_emission",
                        value_a=date_devis,
                        value_b=date_facture,
                        suggestion="Une facture ne peut pas précéder le devis correspondant.",
                    ))
    return alerts


# ─── Règle 5 : Vérification API INSEE (SIRENE) ─────────────────────────────

def _check_insee_registry(records: list[SilverRecord]) -> list[InconsistencyAlert]:
    alerts = []
    insee_api_key = os.getenv('INSEE_API_KEY')
    if not insee_api_key:
        logger.warning('INSEE_API_KEY non configurée, vérification API SIRENE ignorée.')
        return alerts

    headers = {
        'X-INSEE-Api-Key-Integration': insee_api_key,
        'Accept': 'application/json'
    }

    checked_sirens = {}
    checked_sirets = {}

    with httpx.Client(headers=headers, timeout=5.0) as client:
        for rec in records:
            ext = rec.extraction
            siret = ext.siret
            siren = ext.siren
            denomination = None
            etat_ul = None
            official_address = None
            adresse_etab = {}
            
            is_siret_valid_format = siret and re.fullmatch(r'\d{14}', siret.replace(' ', ''))
            
            # FORMATAGE & CHOIX DE L'APPEL
            if is_siret_valid_format:
                clean_siret = siret.replace(' ', '')
                if clean_siret in checked_sirets:
                    data = checked_sirets[clean_siret]
                else:
                    try:
                        url = f'https://api.insee.fr/api-sirene/3.11/siret/{clean_siret}'
                        response = client.get(url)
                        if response.status_code == 404:
                            alerts.append(InconsistencyAlert(
                                id=str(uuid.uuid4()),
                                alert_type=AlertType.SIRET_NOT_FOUND,
                                severity=AlertSeverity.CRITIQUE,
                                description=f"Le SIRET '{clean_siret}' renseigné sur le document est introuvable (faux établissement ou numéro inventé).",
                                document_ids=[rec.document_id],
                                field_in_conflict="siret",
                                value_a=clean_siret,
                                suggestion="Fausse facture détectée. Le SIRET n'existe pas."
                            ))
                            checked_sirets[clean_siret] = None
                            continue
                        response.raise_for_status()
                        data = response.json()
                        checked_sirets[clean_siret] = data
                    except Exception as e:
                        logger.error(f"Erreur API INSEE SIRET {clean_siret}: {e}")
                        checked_sirets[clean_siret] = None
                        continue
                
                if not data:
                    continue
                    
                etab = data.get("etablissement", {})
                periodes_etab = etab.get("periodesEtablissement", [])
                adresse_etab = etab.get("adresseEtablissement", {}) or {}
                official_address = _build_official_address(adresse_etab)
                
                if periodes_etab:
                    etat_etab = periodes_etab[0].get("etatAdministratifEtablissement")
                    if etat_etab == 'F':  # F = Fermé (pour les établissements)
                        alerts.append(InconsistencyAlert(
                            id=str(uuid.uuid4()),
                            alert_type=AlertType.SIRET_CLOSED,
                            severity=AlertSeverity.HAUTE,
                            description=f"Le SIRET '{clean_siret}' correspond à un établissement Fermé.",
                            document_ids=[rec.document_id],
                            field_in_conflict="siret",
                            value_a=clean_siret,
                            suggestion="Document potentiellement antidaté ou faux."
                        ))
                
                # Vérifier aussi la cohérence de l'Unité Légale associée au SIRET
                unite_legale = etab.get("uniteLegale", {})
                etat_ul, denomination = _extract_legal_info(unite_legale)

            else:
                # PAS DE SIRET PRECIS -> ON VERIFIE JUSTE LE SIREN
                if not siren and siret and len(siret) >= 9:
                    siren = siret[:9]
                
                if not siren or not re.fullmatch(r'\d{9}', siren):
                    continue
                    
                if siren in checked_sirens:
                    data = checked_sirens[siren]
                else:
                    try:
                        url = f'https://api.insee.fr/api-sirene/3.11/siren/{siren}'
                        response = client.get(url)
                        if response.status_code == 404:
                            alerts.append(InconsistencyAlert(
                                id=str(uuid.uuid4()),
                                alert_type=AlertType.SIREN_NOT_FOUND,
                                severity=AlertSeverity.CRITIQUE,
                                description=f"Le SIREN '{siren}' est introuvable au registre INSEE.",
                                document_ids=[rec.document_id],
                                field_in_conflict="siren",
                                value_a=siren,
                                suggestion="L'entreprise n'existe pas ou le numéro est factice."
                            ))
                            checked_sirens[siren] = None
                            continue
                            
                        response.raise_for_status()
                        data = response.json()
                        checked_sirens[siren] = data
                    except Exception as e:
                        logger.error(f"Erreur API INSEE SIREN {siren}: {e}")
                        checked_sirens[siren] = None
                        continue
                        
                if not data:
                    continue
                    
                unite_legale = data.get("uniteLegale", {})
                etat_ul, denomination = _extract_legal_info(unite_legale)

            # Vérification Commune (SIREN / SIRET) : Unité Légale et Nom
            if etat_ul == 'C':  # C = Cessée
                alerts.append(InconsistencyAlert(
                    id=str(uuid.uuid4()),
                    alert_type=AlertType.SIREN_COMPANY_CLOSED,
                    severity=AlertSeverity.HAUTE,
                    description=f"L'entreprise rattachée est déclarée 'Cessée' par l'INSEE.",
                    document_ids=[rec.document_id],
                    field_in_conflict="siren" if not is_siret_valid_format else "siret",
                    suggestion="Vérifiez la validité de ce document émis par une entreprise inactive."
                ))
                
            if denomination and ext.emetteur_nom:
                denom_norm = ''.join(e for e in denomination.lower() if e.isalnum())
                em_norm = ''.join(e for e in ext.emetteur_nom.lower() if e.isalnum())
                if em_norm not in denom_norm and denom_norm not in em_norm:
                    alerts.append(InconsistencyAlert(
                        id=str(uuid.uuid4()),
                        alert_type=AlertType.COMPANY_NAME_MISMATCH,
                        severity=AlertSeverity.MOYENNE,
                        description=f"Le nom expéditeur '{ext.emetteur_nom}' diffère du nom officiel INSEE '{denomination}'.",
                        document_ids=[rec.document_id],
                        field_in_conflict="emetteur_nom",
                        value_a=ext.emetteur_nom,
                        value_b=denomination,
                        suggestion="Possible usurpation d'identité ou erreur de nom sur le document."
                    ))

            if _is_address_mismatch(ext.emetteur_adresse, adresse_etab):
                alerts.append(InconsistencyAlert(
                    id=str(uuid.uuid4()),
                    alert_type=AlertType.COMPANY_ADDRESS_MISMATCH,
                    severity=AlertSeverity.MOYENNE,
                    description=(
                        f"L'adresse expéditeur '{ext.emetteur_adresse}' diffère de "
                        f"l'adresse officielle INSEE '{official_address or 'non disponible'}'."
                    ),
                    document_ids=[rec.document_id],
                    field_in_conflict="emetteur_adresse",
                    value_a=ext.emetteur_adresse,
                    value_b=official_address,
                    suggestion="Vérifier la cohérence de l'établissement émetteur (adresse potentiellement falsifiée)."
                ))
    return alerts
