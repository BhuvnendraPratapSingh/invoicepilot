"""Cloud-based OCR service using OpenAI, Anthropic, or Google Vision APIs.

Users provide their own API keys so billing goes to them, not the app owner.
This module handles image-to-text extraction for scanned PDF pages.
"""

import base64
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from io import BytesIO

from app.config import get_ocr_api_key, get_active_ocr_provider


@dataclass
class CloudOCRResult:
    success: bool
    text: str = ""
    error: Optional[str] = None
    provider: Optional[str] = None
    tokens_used: Optional[int] = None  # For cost tracking


def _render_page_to_base64(pdf_path: Path, page_number: int, dpi: int = 200) -> Optional[str]:
    """Render a PDF page to a base64-encoded PNG image."""
    try:
        doc = fitz.open(str(pdf_path))
        if page_number < 1 or page_number > len(doc):
            doc.close()
            return None
        
        page = doc[page_number - 1]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        doc.close()
        
        img_bytes = pix.tobytes("png")
        return base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        return None


def _ocr_with_openai(image_base64: str, api_key: str) -> CloudOCRResult:
    """Extract text from image using OpenAI GPT-4 Vision."""
    try:
        import httpx
        
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",  # Cost-effective vision model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract ALL text from this invoice image exactly as it appears. Include all numbers, dates, amounts, addresses, and text. Preserve the layout structure. Output only the extracted text, no commentary."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 4096,
            },
            timeout=60.0,
        )
        
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", response.text)
            return CloudOCRResult(
                success=False,
                error=f"OpenAI API error ({response.status_code}): {error_detail}",
                provider="openai"
            )
        
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        tokens = data.get("usage", {}).get("total_tokens")
        
        return CloudOCRResult(
            success=True,
            text=text,
            provider="openai",
            tokens_used=tokens
        )
        
    except ImportError:
        return CloudOCRResult(
            success=False,
            error="httpx library not installed. Run: pip install httpx",
            provider="openai"
        )
    except Exception as e:
        return CloudOCRResult(
            success=False,
            error=f"OpenAI OCR failed: {str(e)}",
            provider="openai"
        )


def _ocr_with_anthropic(image_base64: str, api_key: str) -> CloudOCRResult:
    """Extract text from image using Anthropic Claude Vision."""
    try:
        import httpx
        
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                }
                            },
                            {
                                "type": "text",
                                "text": "Extract ALL text from this invoice image exactly as it appears. Include all numbers, dates, amounts, addresses, and text. Preserve the layout structure. Output only the extracted text, no commentary."
                            }
                        ]
                    }
                ],
            },
            timeout=60.0,
        )
        
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", response.text)
            return CloudOCRResult(
                success=False,
                error=f"Anthropic API error ({response.status_code}): {error_detail}",
                provider="anthropic"
            )
        
        data = response.json()
        text = data["content"][0]["text"].strip()
        tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
        
        return CloudOCRResult(
            success=True,
            text=text,
            provider="anthropic",
            tokens_used=tokens
        )
        
    except ImportError:
        return CloudOCRResult(
            success=False,
            error="httpx library not installed. Run: pip install httpx",
            provider="anthropic"
        )
    except Exception as e:
        return CloudOCRResult(
            success=False,
            error=f"Anthropic OCR failed: {str(e)}",
            provider="anthropic"
        )


def _ocr_with_google(image_base64: str, api_key: str) -> CloudOCRResult:
    """Extract text from image using Google Gemini Vision."""
    try:
        import httpx
        
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": "Extract ALL text from this invoice image exactly as it appears. Include all numbers, dates, amounts, addresses, and text. Preserve the layout structure. Output only the extracted text, no commentary."
                            },
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 4096,
                }
            },
            timeout=60.0,
        )
        
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", response.text)
            return CloudOCRResult(
                success=False,
                error=f"Google API error ({response.status_code}): {error_detail}",
                provider="google"
            )
        
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        tokens = data.get("usageMetadata", {}).get("totalTokenCount")
        
        return CloudOCRResult(
            success=True,
            text=text,
            provider="google",
            tokens_used=tokens
        )
        
    except ImportError:
        return CloudOCRResult(
            success=False,
            error="httpx library not installed. Run: pip install httpx",
            provider="google"
        )
    except Exception as e:
        return CloudOCRResult(
            success=False,
            error=f"Google OCR failed: {str(e)}",
            provider="google"
        )


def cloud_ocr_available() -> bool:
    """Check if any cloud OCR provider is configured."""
    provider = get_active_ocr_provider()
    return provider in ("openai", "anthropic", "google")


def get_configured_provider() -> Optional[str]:
    """Get the name of the configured cloud OCR provider, or None."""
    provider = get_active_ocr_provider()
    if provider in ("openai", "anthropic", "google"):
        return provider
    return None


def cloud_ocr_page(pdf_path: Path, page_number: int) -> CloudOCRResult:
    """Run cloud OCR on a single PDF page using the configured provider.
    
    Args:
        pdf_path: Path to the PDF file
        page_number: 1-indexed page number
    
    Returns:
        CloudOCRResult with extracted text or error
    """
    provider = get_active_ocr_provider()
    
    if provider not in ("openai", "anthropic", "google"):
        return CloudOCRResult(
            success=False,
            error="No cloud OCR provider configured. Add an API key in Settings."
        )
    
    api_key = get_ocr_api_key(provider)
    if not api_key:
        return CloudOCRResult(
            success=False,
            error=f"No API key configured for {provider}. Add your key in Settings.",
            provider=provider
        )
    
    # Render page to image
    image_base64 = _render_page_to_base64(pdf_path, page_number)
    if not image_base64:
        return CloudOCRResult(
            success=False,
            error=f"Failed to render page {page_number} to image",
            provider=provider
        )
    
    # Call the appropriate provider
    if provider == "openai":
        return _ocr_with_openai(image_base64, api_key)
    elif provider == "anthropic":
        return _ocr_with_anthropic(image_base64, api_key)
    elif provider == "google":
        return _ocr_with_google(image_base64, api_key)
    
    return CloudOCRResult(success=False, error="Unknown provider")


def cloud_ocr_pdf_pages(pdf_path: Path, page_numbers: list[int]) -> dict[int, CloudOCRResult]:
    """Run cloud OCR on multiple pages of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        page_numbers: List of 1-indexed page numbers
    
    Returns:
        Dict mapping page number to CloudOCRResult
    """
    results = {}
    for page_num in page_numbers:
        results[page_num] = cloud_ocr_page(pdf_path, page_num)
    return results


def validate_api_key(provider: str, api_key: str) -> dict:
    """Validate an API key by checking format and optionally making a minimal API call.
    
    Returns dict with 'valid' bool and 'error' message if invalid.
    """
    if not api_key or len(api_key) < 10:
        return {"valid": False, "error": "API key is too short"}
    
    # Format validation (basic checks)
    if provider == "openai":
        if not (api_key.startswith("sk-") or api_key.startswith("sk-proj-")):
            return {"valid": False, "error": "OpenAI keys should start with 'sk-'"}
    elif provider == "anthropic":
        if not api_key.startswith("sk-ant-"):
            return {"valid": False, "error": "Anthropic keys should start with 'sk-ant-'"}
    elif provider == "google":
        # Google API keys don't have a consistent prefix
        if len(api_key) < 20:
            return {"valid": False, "error": "Google API key seems too short"}
    
    # Try to validate with actual API call (but don't fail if network issues)
    try:
        import httpx
        
        if provider == "openai":
            response = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return {"valid": True}
            elif response.status_code == 401:
                return {"valid": False, "error": "Invalid API key (authentication failed)"}
            else:
                # Other errors - accept the key anyway (might be rate limit, etc.)
                return {"valid": True, "note": f"Key format valid, API returned {response.status_code}"}
        
        elif provider == "anthropic":
            # Anthropic doesn't have a simple validation endpoint
            # Format already checked above
            return {"valid": True, "note": "Key format valid"}
        
        elif provider == "google":
            # Google API keys can have various formats, try to validate
            try:
                response = httpx.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    return {"valid": True}
                elif response.status_code in (400, 401, 403):
                    # Only reject if clearly invalid
                    error_msg = response.json().get("error", {}).get("message", "")
                    if "API key" in error_msg.lower() or "invalid" in error_msg.lower():
                        return {"valid": False, "error": "Invalid API key"}
                    # Otherwise accept it
                    return {"valid": True, "note": f"Key saved (API returned {response.status_code})"}
                else:
                    return {"valid": True, "note": f"Key saved, API returned {response.status_code}"}
            except Exception:
                # Network error - accept based on format
                if len(api_key) >= 20:
                    return {"valid": True, "note": "Key format valid (network check skipped)"}
                return {"valid": False, "error": "Key seems too short"}
        
        return {"valid": True, "note": "Key format appears valid"}
    
    except ImportError:
        # httpx not installed - accept based on format
        return {"valid": True, "note": "Key format valid (network validation skipped)"}
    except Exception as e:
        # Network error - accept based on format validation
        return {"valid": True, "note": f"Key format valid (network check failed: {type(e).__name__})"}
