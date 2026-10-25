"""PDF reading, validation, and text extraction using PyMuPDF."""

import hashlib
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from app.config import settings


# Minimum characters to consider a page as having usable text
MIN_TEXT_CHARS = 50


@dataclass
class PageResult:
    page_number: int  # 1-indexed
    text: str
    method: str  # NATIVE_TEXT or OCR
    char_count: int
    has_usable_text: bool
    is_image_only: bool


@dataclass
class PDFReadResult:
    success: bool
    error: Optional[str] = None
    sha256_hash: Optional[str] = None
    page_count: int = 0
    file_size_bytes: int = 0
    pages: list[PageResult] = field(default_factory=list)
    needs_ocr_pages: list[int] = field(default_factory=list)  # 1-indexed
    is_encrypted: bool = False
    full_text: str = ""


def validate_and_read_pdf(file_path: Path) -> PDFReadResult:
    """Validate a PDF file and extract text from each page.
    
    Returns native text for text-bearing pages.
    Identifies pages needing OCR (insufficient text).
    """
    # Check file exists and size
    if not file_path.exists():
        return PDFReadResult(success=False, error="File not found")

    file_size = file_path.stat().st_size
    if file_size > settings.max_file_size_bytes:
        return PDFReadResult(
            success=False,
            error=f"File size {file_size:,} bytes exceeds limit of {settings.max_file_size_bytes:,} bytes",
            file_size_bytes=file_size,
        )

    if file_size == 0:
        return PDFReadResult(success=False, error="File is empty")

    # Calculate SHA-256
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    file_hash = sha256.hexdigest()

    # Try opening as PDF
    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        return PDFReadResult(
            success=False,
            error=f"Cannot open PDF: {str(e)}",
            sha256_hash=file_hash,
            file_size_bytes=file_size,
        )

    # Check encryption
    if doc.is_encrypted:
        doc.close()
        return PDFReadResult(
            success=False,
            error="PDF is encrypted/password-protected",
            sha256_hash=file_hash,
            file_size_bytes=file_size,
            is_encrypted=True,
        )

    # Check page count
    page_count = len(doc)
    if page_count == 0:
        doc.close()
        return PDFReadResult(
            success=False,
            error="PDF has no pages",
            sha256_hash=file_hash,
            file_size_bytes=file_size,
        )

    if page_count > settings.max_pages:
        doc.close()
        return PDFReadResult(
            success=False,
            error=f"PDF has {page_count} pages, exceeding limit of {settings.max_pages}",
            sha256_hash=file_hash,
            file_size_bytes=file_size,
            page_count=page_count,
        )

    # Extract text page by page
    pages = []
    needs_ocr = []
    all_text_parts = []

    for i in range(page_count):
        page = doc[i]
        text = page.get_text("text").strip()
        char_count = len(text)
        has_usable = char_count >= MIN_TEXT_CHARS

        # Check if page has images (potential scan)
        image_list = page.get_images(full=True)
        is_image_only = len(image_list) > 0 and not has_usable

        page_num = i + 1  # 1-indexed
        method = "NATIVE_TEXT" if has_usable else "PENDING_OCR"

        if not has_usable:
            needs_ocr.append(page_num)

        pages.append(PageResult(
            page_number=page_num,
            text=text if has_usable else "",
            method=method,
            char_count=char_count,
            has_usable_text=has_usable,
            is_image_only=is_image_only,
        ))

        if has_usable:
            all_text_parts.append(text)

    doc.close()

    return PDFReadResult(
        success=True,
        sha256_hash=file_hash,
        page_count=page_count,
        file_size_bytes=file_size,
        pages=pages,
        needs_ocr_pages=needs_ocr,
        full_text="\n\n".join(all_text_parts),
    )


def render_page_image(file_path: Path, page_number: int, dpi: int = 150) -> Optional[Path]:
    """Render a PDF page as a PNG image for preview/evidence display."""
    try:
        doc = fitz.open(str(file_path))
        if page_number < 1 or page_number > len(doc):
            doc.close()
            return None

        page = doc[page_number - 1]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)

        output_dir = settings.page_images_path
        output_path = output_dir / f"{file_path.stem}_page_{page_number}.png"
        pix.save(str(output_path))

        doc.close()
        return output_path
    except Exception:
        return None
