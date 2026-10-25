"""OCR service using Tesseract via pytesseract for scanned pages.

Also integrates with cloud OCR providers (OpenAI, Anthropic, Google) when configured.
Cloud OCR uses user-provided API keys so billing goes to them.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from io import BytesIO

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
    # Auto-detect Tesseract on Windows user-local installs
    import platform, os
    if platform.system() == "Windows":
        _candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for _p in _candidates:
            if os.path.isfile(_p):
                pytesseract.pytesseract.tesseract_cmd = _p
                break
except ImportError:
    TESSERACT_AVAILABLE = False


@dataclass
class OCRResult:
    success: bool
    text: str = ""
    error: Optional[str] = None
    confidence: Optional[float] = None  # Diagnostic signal only, not proof
    method: str = "tesseract"  # tesseract, openai, anthropic, google


def check_tesseract() -> bool:
    """Check if Tesseract is available on the system."""
    if not TESSERACT_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def check_any_ocr_available() -> dict:
    """Check all OCR options and return availability status."""
    from app.config import get_active_ocr_provider, get_ocr_api_key
    
    result = {
        "tesseract": check_tesseract(),
        "cloud_configured": False,
        "active_provider": None,
        "providers": {}
    }
    
    # Check cloud providers
    for provider in ["openai", "anthropic", "google"]:
        key = get_ocr_api_key(provider)
        result["providers"][provider] = bool(key)
        if key:
            result["cloud_configured"] = True
    
    result["active_provider"] = get_active_ocr_provider()
    result["any_available"] = result["tesseract"] or result["cloud_configured"]
    
    return result


def ocr_page(pdf_path: Path, page_number: int, dpi: int = 300) -> OCRResult:
    """Run OCR on a single PDF page using the best available method.
    
    Priority (based on config):
    1. Cloud OCR if configured (OpenAI/Anthropic/Google)
    2. Local Tesseract as fallback
    
    Args:
        pdf_path: Path to the PDF file
        page_number: 1-indexed page number
        dpi: Resolution for rendering (higher = better OCR but slower)
    """
    from app.config import get_active_ocr_provider
    
    provider = get_active_ocr_provider()
    
    # Try cloud OCR first if configured
    if provider in ("openai", "anthropic", "google"):
        from app.services.cloud_ocr import cloud_ocr_page
        cloud_result = cloud_ocr_page(pdf_path, page_number)
        if cloud_result.success:
            return OCRResult(
                success=True,
                text=cloud_result.text,
                method=cloud_result.provider or provider,
            )
        # Cloud failed - fall through to Tesseract if available
        if not check_tesseract():
            return OCRResult(
                success=False,
                error=cloud_result.error,
                method=provider
            )
        # Continue to Tesseract fallback
    
    # Use Tesseract (local)
    if not TESSERACT_AVAILABLE:
        return OCRResult(
            success=False,
            error="No OCR available. Either install Tesseract locally or configure a cloud API key (OpenAI/Anthropic/Google) in Settings.",
            method="none"
        )

    if not check_tesseract():
        return OCRResult(
            success=False,
            error="Tesseract OCR engine not found. Install from: https://github.com/tesseract-ocr/tesseract or configure a cloud API key in Settings.",
            method="tesseract"
        )

    try:
        doc = fitz.open(str(pdf_path))
        if page_number < 1 or page_number > len(doc):
            doc.close()
            return OCRResult(success=False, error=f"Page {page_number} out of range", method="tesseract")

        page = doc[page_number - 1]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        doc.close()

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(BytesIO(img_data))

        # Run OCR
        text = pytesseract.image_to_string(img)

        # Get confidence data (diagnostic only)
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        except Exception:
            avg_confidence = None

        return OCRResult(
            success=True,
            text=text.strip(),
            confidence=avg_confidence,
            method="tesseract"
        )

    except Exception as e:
        return OCRResult(success=False, error=f"OCR failed: {str(e)}", method="tesseract")


def ocr_pdf_pages(pdf_path: Path, page_numbers: list[int]) -> dict[int, OCRResult]:
    """Run OCR on multiple pages of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        page_numbers: List of 1-indexed page numbers
    
    Returns:
        Dict mapping page number to OCR result
    """
    results = {}
    for page_num in page_numbers:
        results[page_num] = ocr_page(pdf_path, page_num)
    return results
