from unittest.mock import MagicMock, patch

import pytest

from app.services.ocr import OcrResult, extract_text_from_file, extract_text_from_pdf_path


@pytest.fixture
def mock_pdf_path(tmp_path):
    p = tmp_path / "test.pdf"
    p.write_bytes(b"%PDF-1.4 test")
    return p

def test_extract_text_native_pdf(mock_pdf_path):
    """Test when pypdf successfully extracts text."""
    with patch("app.services.ocr.PdfReader") as mock_reader_cls, \
         patch("app.services.ocr.convert_from_path") as mock_convert, \
         patch("app.services.ocr.image_to_string") as mock_ocr:
        
        # Setup pypdf to return text
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello from pypdf"
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader
        
        result = extract_text_from_pdf_path(mock_pdf_path)
        
        assert "Hello from pypdf" in result.text
        assert result.page_count == 1
        # Tesseract should NOT be called if pypdf worked
        mock_convert.assert_not_called()
        mock_ocr.assert_not_called()

def test_extract_text_scanned_pdf(mock_pdf_path):
    """Test when pypdf fails (empty text) and falls back to Tesseract."""
    with patch("app.services.ocr.PdfReader") as mock_reader_cls, \
         patch("app.services.ocr.convert_from_path") as mock_convert, \
         patch("app.services.ocr.image_to_string") as mock_ocr, \
         patch("app.services.ocr._check_dependencies", return_value=[]):
        
        # Setup pypdf to return NO text
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "   " # Whitespace
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader
        
        # Setup Tesseract
        mock_convert.return_value = [MagicMock()] # One image
        mock_ocr.return_value = "Hello from Tesseract"
        
        result = extract_text_from_pdf_path(mock_pdf_path)
        
        assert "Hello from Tesseract" in result.text
        assert result.page_count == 1
        # Tesseract SHOULD be called
        mock_convert.assert_called_once()
        mock_ocr.assert_called_once()

def test_ocr_result_bool():
    res_empty = OcrResult("", 0)
    res_text = OcrResult("  hello  ", 1)
    res_whitespace = OcrResult("\n ", 1)
    
    assert not res_empty
    assert res_text
    assert not res_whitespace

def test_extract_text_image_path(tmp_path):
    """Test when extracting text directly from an image."""
    p = tmp_path / "test.png"
    p.write_bytes(b"dummy image data")
    
    with patch("app.services.ocr.Image.open") as mock_open_func, \
         patch("app.services.ocr.image_to_string") as mock_ocr, \
         patch("app.services.ocr.shutil.which", return_value="tesseract_path"):
        
        mock_open_func.return_value = MagicMock()
        mock_ocr.return_value = "Hello from Image Tesseract"
        
        result = extract_text_from_file(p)
        
        assert "Hello from Image Tesseract" in result.text
        assert result.page_count == 1
        mock_open_func.assert_called_once_with(str(p))
        mock_ocr.assert_called_once()
