import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from app.services.ocr import extract_text_from_pdf_path, OcrResult

@pytest.fixture
def mock_pdf_path(tmp_path):
    p = tmp_path / "test.pdf"
    p.write_bytes(b"%PDF-1.4 test")
    return p

def test_extract_text_native_pdf(mock_pdf_path):
    """Test when pypdf successfully extracts text."""
    with patch("app.services.ocr.PdfReader") as MockReader, \
         patch("app.services.ocr.convert_from_path") as MockConvert, \
         patch("app.services.ocr.image_to_string") as MockOcr:
        
        # Setup pypdf to return text
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello from pypdf"
        mock_reader.pages = [mock_page]
        MockReader.return_value = mock_reader
        
        result = extract_text_from_pdf_path(mock_pdf_path)
        
        assert "Hello from pypdf" in result.text
        assert result.page_count == 1
        # Tesseract should NOT be called if pypdf worked
        MockConvert.assert_not_called()
        MockOcr.assert_not_called()

def test_extract_text_scanned_pdf(mock_pdf_path):
    """Test when pypdf fails (empty text) and falls back to Tesseract."""
    with patch("app.services.ocr.PdfReader") as MockReader, \
         patch("app.services.ocr.convert_from_path") as MockConvert, \
         patch("app.services.ocr.image_to_string") as MockOcr:
        
        # Setup pypdf to return NO text
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "   " # Whitespace
        mock_reader.pages = [mock_page]
        MockReader.return_value = mock_reader
        
        # Setup Tesseract
        MockConvert.return_value = [MagicMock()] # One image
        MockOcr.return_value = "Hello from Tesseract"
        
        result = extract_text_from_pdf_path(mock_pdf_path)
        
        assert "Hello from Tesseract" in result.text
        assert result.page_count == 1
        # Tesseract SHOULD be called
        MockConvert.assert_called_once()
        MockOcr.assert_called_once()

def test_ocr_result_bool():
    res_empty = OcrResult("", 0)
    res_text = OcrResult("  hello  ", 1)
    res_whitespace = OcrResult("\n ", 1)
    
    assert not res_empty
    assert res_text
    assert not res_whitespace
