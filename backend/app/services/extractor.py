"""Service d'extraction : extrait les informations clés via LLM."""
import logging
import os
import re
from decimal import Decimal

from app.schemas.extraction import ExtractedData, MonetaryAmount
from app.services.llm_json import extract_json_object, preview_llm_output
from groq import Groq
from ollama import Client as OllamaClient

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Tu es un expert comptable français spécialisé 
dans l'analyse de documents administratifs.
Extrait les informations clés du texte suivant.

Texte du document :
---
{text}
---

Réponds UNIQUEMENT avec un JSON valide dans ce format exact 
(utilise null si l'information est absente) :
{{
  "siren": "<9 chiffres ou null>",
  "siret": "<14 chiffres ou null>",
  "emetteur_nom": "<nom de l'entité émettrice ou null>",
  "emetteur_adresse": "<adresse complète de l'émetteur ou null>",
  "destinataire_nom": "<nom du destinataire ou null>",
  "destinataire_adresse": "<adresse du destinataire ou null>",
  "montant_ht": "<montant HT en chiffres uniquement, ex: 1500.00, ou null>",
  "montant_tva": "<montant TVA en chiffres uniquement ou null>",
  "montant_ttc": "<montant TTC en chiffres uniquement ou null>",
  "date_emission": "<date au format YYYY-MM-DD ou null>",
  "date_echeance": "<date au format YYYY-MM-DD ou null>",
  "numero_document": "<numéro de facture/devis/attestation ou null>"
}}

Important : 
- SIREN = 9 chiffres UNIQUEMENT (sans espaces ni tirets)
- SIRET = 14 chiffres UNIQUEMENT (sans espaces ni tirets)
- Les montants doivent être des nombres décimaux (ex: 1500.00)
"""


def extract_document_data(text: str) -> ExtractedData:
    """Extrait les informations clés d'un document via le LLM configuré."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        raw = _call_groq(text)
    else:
        raw = _call_ollama(text)

    return _parse_extraction_response(raw, text)


def _call_ollama(text: str) -> str:
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    client = OllamaClient(host=base_url)
    prompt = EXTRACTION_PROMPT.format(text=text[:4000])
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0},
    )
    return response.message.content


def _call_groq(text: str) -> str:
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = EXTRACTION_PROMPT.format(text=text[:4000])
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


def _clean_numeric(value: str | None) -> Decimal | None:
    """Nettoie une chaîne monétaire et retourne un Decimal."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.,]", "", str(value)).replace(",", ".")
    try:
        return Decimal(cleaned) if cleaned else None
    except Exception:
        return None


def _clean_siren(value: str | None) -> str | None:
    """Garde uniquement les chiffres d'un SIREN/SIRET."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if digits else None


def _parse_extraction_response(raw: str, original_text: str) -> ExtractedData:
    try:
        data = extract_json_object(raw)
        if not data:
            raise ValueError("Aucun objet JSON valide trouvé dans la réponse")

        siren_raw = _clean_siren(data.get("siren"))
        siret_raw = _clean_siren(data.get("siret"))

        # Si SIREN absent mais SIRET présent, déduire le SIREN (9 premiers chiffres)
        if not siren_raw and siret_raw and len(siret_raw) == 14:
            siren_raw = siret_raw[:9]

        montants = MonetaryAmount(
            ht=_clean_numeric(data.get("montant_ht")),
            tva=_clean_numeric(data.get("montant_tva")),
            ttc=_clean_numeric(data.get("montant_ttc")),
        )

        # Validation silencieuse du SIREN (pas d'exception, log seulement)
        siren_valid = siren_raw and re.fullmatch(r"\d{9}", siren_raw)
        siret_valid = siret_raw and re.fullmatch(r"\d{14}", siret_raw)

        return ExtractedData(
            siren=siren_raw if siren_valid else None,
            siret=siret_raw if siret_valid else None,
            emetteur_nom=data.get("emetteur_nom"),
            emetteur_adresse=data.get("emetteur_adresse"),
            destinataire_nom=data.get("destinataire_nom"),
            destinataire_adresse=data.get("destinataire_adresse"),
            montants=montants,
            date_emission=data.get("date_emission"),
            date_echeance=data.get("date_echeance"),
            numero_document=data.get("numero_document"),
            raw_text=original_text,
        )

    except (KeyError, TypeError, ValueError) as exc:
        logger.error(
            "Impossible de parser la réponse LLM extraction : %s | extrait=%s",
            exc,
            preview_llm_output(raw),
        )
        return ExtractedData(raw_text=original_text)
