"""Service LLM : classification de documents (Ollama ou Groq)."""
import logging
import os

from app.schemas.classification import ClassificationResult
from app.schemas.document import DocumentType
from app.services.llm_json import extract_json_object, preview_llm_output
from groq import Groq
from ollama import Client as OllamaClient

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Tu es un expert administratif français.
Analyse le texte suivant extrait d'un document administratif et classifie-le.

Texte du document :
---
{text}
---

Réponds UNIQUEMENT avec un JSON valide dans ce format exact :
{{
  "document_type": "<facture|devis|attestation|autre>",
  "confidence": <float entre 0.0 et 1.0>,
  "reasoning": "<explication brève en français>"
}}

Règles de classification :
- "facture" : document de facturation avec montant dû, numéro de facture
- "devis" : proposition commerciale préalable à une facture
- "attestation" : document officiel certifiant un fait (attestation Urssaf, certificat, etc.)
- "autre" : tout autre document administratif
"""


def classify_document(text: str) -> ClassificationResult:
    """Classifie un document via le LLM configuré (Ollama ou Groq)."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        return _classify_with_groq(text)
    return _classify_with_ollama(text)


def _classify_with_ollama(text: str) -> ClassificationResult:
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    client = OllamaClient(host=base_url)
    prompt = CLASSIFICATION_PROMPT.format(text=text[:3000])

    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0},
    )
    raw = response.message.content
    return _parse_classification_response(raw, model_used=f"ollama/{model}")


def _classify_with_groq(text: str) -> ClassificationResult:
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    api_key = os.getenv("GROQ_API_KEY")

    client = Groq(api_key=api_key)
    prompt = CLASSIFICATION_PROMPT.format(text=text[:3000])

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return _parse_classification_response(raw, model_used=f"groq/{model}")


def _parse_classification_response(raw: str, model_used: str) -> ClassificationResult:
    try:
        data = extract_json_object(raw)
        if not data:
            raise ValueError("Aucun objet JSON valide trouvé dans la réponse")

        doc_type_str = data.get("document_type", "autre").lower()
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            logger.warning("Type de document inconnu '%s', fallback → autre", doc_type_str)
            doc_type = DocumentType.AUTRE

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            document_type=doc_type,
            confidence=confidence,
            model_used=model_used,
            raw_response=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.error(
            "Impossible de parser la réponse LLM classification : %s | extrait=%s",
            exc,
            preview_llm_output(raw),
        )
        return ClassificationResult(
            document_type=DocumentType.AUTRE,
            confidence=0.0,
            model_used=model_used,
            raw_response=raw,
        )
