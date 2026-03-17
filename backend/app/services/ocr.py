"""Service OCR : conversion PDF → texte via pypdf (fallback) ou Tesseract."""

import io
import logging
import shutil
from pathlib import Path

from pdf2image import convert_from_bytes, convert_from_path
from pypdf import PdfReader
from pytesseract import image_to_string

logger = logging.getLogger(__name__)


class OcrResult:
    def __init__(self, text: str, page_count: int, success: bool = True, error: str | None = None):
        self.text = text
        self.page_count = page_count
        self.success = success
        self.error = error

    def __bool__(self) -> bool:
        return bool(self.text.strip())


def _check_dependencies() -> list[str]:
    """Vérifie si Poppler et Tesseract sont installés."""
    missing = []
    if not shutil.which("pdftoppm"):
        missing.append("poppler-utils (pdftoppm)")
    if not shutil.which("tesseract"):
        missing.append("tesseract-ocr")
    return missing


def _ocr_with_tesseract(pdf_input: Path | bytes, lang: str = "fra") -> tuple[str, str | None]:
    """
    Effectue l'OCR sur un PDF (chemin ou bytes) en le convertissant en images.
    Retourne (texte, erreur_éventuelle).
    """
    missing = _check_dependencies()
    if missing:
        err_msg = f"Dépendances système manquantes pour l'OCR : {', '.join(missing)}"
        logger.error(err_msg)
        return "", err_msg

    try:
        if isinstance(pdf_input, Path):
            images = convert_from_path(str(pdf_input))
        else:
            images = convert_from_bytes(pdf_input)

        pages_text = []
        for image in images:
            text = image_to_string(image, lang=lang)
            pages_text.append(text)

        return "\n\n".join(pages_text), None
    except Exception as exc:
        err_msg = f"Erreur lors de l'OCR Tesseract : {exc}"
        logger.error(err_msg)
        if "poppler" in str(exc).lower() or "page count" in str(exc).lower():
            err_msg = "Poppler n'est pas installé ou n'est pas dans le PATH."
        return "", err_msg


def extract_text_from_pdf_path(pdf_path: Path, lang: str = "fra") -> OcrResult:
    """
    Extrait le texte d'un fichier PDF.
    Utilise pypdf en priorité (texte natif).
    Bascule sur Tesseract pour les PDF scannés (texte vide).
    """
    try:
        reader = PdfReader(str(pdf_path))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            pages_text.append(text or "")

        full_text = "\n\n".join(pages_text).strip()
        page_count = len(reader.pages)

        # Fallback intelligent
        if not full_text and page_count > 0:
            logger.info("PDF vide détecté (possible scan), passage à Tesseract OCR...")
            ocr_text, err = _ocr_with_tesseract(pdf_path, lang=lang)
            if err:
                return OcrResult(text="", page_count=page_count, success=False, error=err)
            full_text = ocr_text

        return OcrResult(text=full_text, page_count=page_count)
    except Exception as exc:
        logger.error("Erreur lors de l'extraction de texte PDF via path : %s", exc)
        return OcrResult(text="", page_count=0, success=False, error=str(exc))


def extract_text_from_bytes(pdf_bytes: bytes, lang: str = "fra") -> OcrResult:
    """Extrait le texte d'un PDF en mémoire (bytes) via pypdf avec fallback Tesseract."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            pages_text.append(text or "")

        full_text = "\n\n".join(pages_text).strip()
        page_count = len(reader.pages)

        # Fallback intelligent
        if not full_text and page_count > 0:
            logger.info("PDF-bytes vide détecté (possible scan), passage à Tesseract OCR...")
            ocr_text, err = _ocr_with_tesseract(pdf_bytes, lang=lang)
            if err:
                return OcrResult(text="", page_count=page_count, success=False, error=err)
            full_text = ocr_text

        return OcrResult(text=full_text, page_count=page_count)
    except Exception as exc:
        logger.error("Erreur lors de l'extraction de texte PDF via bytes : %s", exc)
        return OcrResult(text="", page_count=0, success=False, error=str(exc))
