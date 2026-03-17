from app.schemas.document import DocumentType
from app.services.classifier import _parse_classification_response
from app.services.extractor import _parse_extraction_response


def test_classifier_parses_json_inside_code_fence():
    raw = (
        "Reponse:\n"
        "```json\n"
        '{"document_type":"facture","confidence":0.91,"reasoning":"OK"}\n'
        "```"
    )

    result = _parse_classification_response(raw, model_used="ollama/gemma3:4b")

    assert result.document_type == DocumentType.FACTURE
    assert result.confidence == 0.91


def test_extractor_parses_json_with_prefix_text():
    raw = (
        "Voici les donnees extraites:\n"
        '{"siren":"123-456","siret":"38012986648625","emetteur_nom":"BAD SIREN ENT",'
        '"montant_ttc":"100.00"}'
    )

    result = _parse_extraction_response(raw, original_text="facture test")

    assert result.siret == "38012986648625"
    assert result.siren is None
    assert result.emetteur_nom == "BAD SIREN ENT"
    assert str(result.montants.ttc) == "100.00"
