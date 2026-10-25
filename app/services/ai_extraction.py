"""AI-powered field extraction using cloud LLM APIs (Gemini, OpenAI, Anthropic).

Sends invoice text to a vision/language model and gets back structured fields.
Falls back gracefully — caller should use local regex extraction if this fails.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.services.extraction import ExtractionResult, FieldExtraction


# ─── Prompt ─────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are an expert accounts payable document processor. Extract ALL fields from this invoice text.

Return a JSON object with EXACTLY these keys (use null for missing fields):

{
  "vendor_name": "string — full legal name of the vendor/supplier",
  "vendor_tax_id": "string — EIN/TIN/Tax ID (format: XX-XXXXXXX)",
  "vendor_address": "string — full vendor address",
  "invoice_number": "string — the invoice number/reference",
  "invoice_date": "string — invoice date as written",
  "due_date": "string — payment due date as written",
  "currency": "string — 3-letter code like USD, EUR",
  "po_reference": "string — purchase order reference (format: PO-XXXX)",
  "subtotal": "number — subtotal amount in dollars (e.g. 2500.00)",
  "discount": "number — discount amount in dollars",
  "shipping": "number — shipping/freight amount in dollars",
  "tax": "number — tax amount in dollars",
  "gross_total": "number — total/grand total/amount due in dollars",
  "tax_treatment": "string — EXCLUSIVE or INCLUSIVE",
  "line_items": [
    {"description": "string", "quantity": "number or null", "unit_price": "number or null", "amount": "number"}
  ]
}

RULES:
- Extract ONLY what is explicitly in the document. Do not guess or fabricate.
- For money fields, return the decimal dollar amount (e.g. 2500.00 not 250000).
- If a PO reference exists, normalize it to PO-XXXX format.
- If currency is not stated but $ signs are used, return "USD".
- Return ONLY valid JSON, no markdown, no commentary.

INVOICE TEXT:
"""


def _parse_ai_money_to_cents(value) -> Optional[int]:
    """Convert AI-returned dollar amount to cents."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace('$', '').replace(',', '').strip()
        d = Decimal(str(value))
        return int(d * 100)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _make_field(name: str, value, method: str = "AI_EXTRACTION") -> Optional[FieldExtraction]:
    """Create a FieldExtraction from an AI-returned value."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    
    str_value = str(value).strip()
    return FieldExtraction(
        field_name=name,
        raw_text=str_value,
        normalized_value=str_value,
        page_number=1,
        text_span=str_value,
        method=method,
        verification_status="VERIFIED",
        is_explicitly_present=True,
    )


def _make_money_field(name: str, value, method: str = "AI_EXTRACTION") -> Optional[FieldExtraction]:
    """Create a FieldExtraction for a money field (stored as cents)."""
    cents = _parse_ai_money_to_cents(value)
    if cents is None or cents <= 0:
        return None
    
    return FieldExtraction(
        field_name=name,
        raw_text=str(value),
        normalized_value=str(cents),
        page_number=1,
        text_span=str(value),
        method=method,
        verification_status="VERIFIED",
        is_explicitly_present=True,
    )


def _extract_json_from_response(text: str) -> Optional[dict]:
    """Robustly extract JSON from AI response (handles markdown fences, etc.)."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting from markdown code fence
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try finding first { ... } block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def _call_gemini(text: str, api_key: str) -> Optional[dict]:
    """Call Google Gemini API for extraction."""
    import httpx
    
    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{
                "parts": [{"text": EXTRACTION_PROMPT + text}]
            }],
            "generationConfig": {
                "maxOutputTokens": 4096,
                "temperature": 0.1,  # Low temperature for precise extraction
            }
        },
        timeout=60.0,
    )
    
    if response.status_code != 200:
        error = response.json().get("error", {}).get("message", response.text)
        raise Exception(f"Gemini API error ({response.status_code}): {error}")
    
    data = response.json()
    ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json_from_response(ai_text)


def _call_openai(text: str, api_key: str) -> Optional[dict]:
    """Call OpenAI API for extraction."""
    import httpx
    
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You extract structured data from invoices. Return only valid JSON."},
                {"role": "user", "content": EXTRACTION_PROMPT + text}
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        },
        timeout=60.0,
    )
    
    if response.status_code != 200:
        error = response.json().get("error", {}).get("message", response.text)
        raise Exception(f"OpenAI API error ({response.status_code}): {error}")
    
    data = response.json()
    ai_text = data["choices"][0]["message"]["content"]
    return _extract_json_from_response(ai_text)


def _call_anthropic(text: str, api_key: str) -> Optional[dict]:
    """Call Anthropic API for extraction."""
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
                {"role": "user", "content": EXTRACTION_PROMPT + text}
            ],
        },
        timeout=60.0,
    )
    
    if response.status_code != 200:
        error = response.json().get("error", {}).get("message", response.text)
        raise Exception(f"Anthropic API error ({response.status_code}): {error}")
    
    data = response.json()
    ai_text = data["content"][0]["text"]
    return _extract_json_from_response(ai_text)


def get_extraction_provider() -> Optional[tuple[str, str]]:
    """Get the best available AI extraction provider and its API key.
    
    Returns (provider_name, api_key) or None if no provider available.
    Checks the same keys used for OCR — one key serves both purposes.
    """
    from app.config import get_ocr_api_key
    
    # Priority: Google (cheapest) > OpenAI > Anthropic
    for provider in ("google", "openai", "anthropic"):
        key = get_ocr_api_key(provider)
        if key:
            return (provider, key)
    
    return None


def ai_extract_fields(page_texts: dict[int, str], method_per_page: dict[int, str] = None) -> Optional[ExtractionResult]:
    """Extract invoice fields using AI (Gemini/OpenAI/Anthropic).
    
    Returns ExtractionResult on success, or None if AI is unavailable or fails.
    Caller should fall back to local extraction on None.
    """
    provider_info = get_extraction_provider()
    if not provider_info:
        return None
    
    provider, api_key = provider_info
    
    if method_per_page is None:
        method_per_page = {p: "NATIVE_TEXT" for p in page_texts}
    
    # Combine all page texts
    all_text = "\n\n".join(
        f"--- Page {p} ---\n{text}" 
        for p, text in sorted(page_texts.items())
    )
    
    # Truncate to avoid token limits (roughly 15k chars ≈ 4k tokens)
    if len(all_text) > 15000:
        all_text = all_text[:15000] + "\n[... truncated ...]"
    
    try:
        # Call the appropriate provider
        if provider == "google":
            ai_data = _call_gemini(all_text, api_key)
        elif provider == "openai":
            ai_data = _call_openai(all_text, api_key)
        elif provider == "anthropic":
            ai_data = _call_anthropic(all_text, api_key)
        else:
            return None
        
        if not ai_data or not isinstance(ai_data, dict):
            return None
        
        # Build ExtractionResult from AI response
        method = f"AI_{provider.upper()}"
        result = ExtractionResult(extraction_method=f"ai_{provider}")
        
        result.vendor_name = _make_field("vendor_name", ai_data.get("vendor_name"), method)
        result.vendor_tax_id = _make_field("vendor_tax_id", ai_data.get("vendor_tax_id"), method)
        result.vendor_address = _make_field("vendor_address", ai_data.get("vendor_address"), method)
        result.invoice_number = _make_field("invoice_number", ai_data.get("invoice_number"), method)
        result.invoice_date = _make_field("invoice_date", ai_data.get("invoice_date"), method)
        result.due_date = _make_field("due_date", ai_data.get("due_date"), method)
        result.currency = _make_field("currency", ai_data.get("currency"), method)
        
        # PO reference — normalize
        po_ref = ai_data.get("po_reference")
        if po_ref:
            po_str = str(po_ref).strip().upper()
            # Normalize to PO-XXXX format
            po_match = re.search(r'(PO[-\s]?\d+)', po_str, re.IGNORECASE)
            if po_match:
                po_str = po_match.group(1).replace(' ', '-')
                if not po_str.startswith('PO-'):
                    po_str = 'PO-' + po_str.replace('PO', '')
            result.po_reference = _make_field("po_reference", po_str, method)
        
        # Money fields
        result.subtotal = _make_money_field("subtotal", ai_data.get("subtotal"), method)
        result.discount = _make_money_field("discount", ai_data.get("discount"), method)
        result.shipping = _make_money_field("shipping", ai_data.get("shipping"), method)
        result.tax = _make_money_field("tax", ai_data.get("tax"), method)
        result.gross_total = _make_money_field("gross_total", ai_data.get("gross_total"), method)
        
        # Tax treatment
        tax_treatment = ai_data.get("tax_treatment")
        if tax_treatment:
            result.tax_treatment = FieldExtraction(
                field_name="tax_treatment",
                raw_text=str(tax_treatment),
                normalized_value=str(tax_treatment).upper(),
                method=method,
                verification_status="VERIFIED",
                is_explicitly_present=True,
            )
        
        # Line items
        raw_items = ai_data.get("line_items", [])
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict) and item.get("description"):
                    amount_cents = _parse_ai_money_to_cents(item.get("amount"))
                    if amount_cents and amount_cents > 0:
                        result.line_items.append({
                            'description': str(item['description']),
                            'amount_cents': amount_cents,
                            'amount_display': f"${Decimal(amount_cents)/Decimal(100):,.2f}",
                            'quantity': item.get('quantity'),
                            'unit_price': item.get('unit_price'),
                            'raw_text': str(item),
                        })
        
        # Derive tax treatment if not explicitly set
        if result.tax_treatment is None:
            subtotal_cents = int(result.subtotal.normalized_value) if result.subtotal else None
            tax_cents = int(result.tax.normalized_value) if result.tax else None
            gross_cents = int(result.gross_total.normalized_value) if result.gross_total else None
            
            if subtotal_cents is not None:
                result.tax_treatment = FieldExtraction(
                    field_name="tax_treatment",
                    raw_text="TAX_EXCLUSIVE",
                    normalized_value="EXCLUSIVE",
                    method="DERIVED_ARITHMETIC",
                    verification_status="VERIFIED" if tax_cents is not None else "UNCERTAIN",
                    is_explicitly_present=False,
                )
            elif gross_cents is not None and tax_cents is not None:
                result.tax_treatment = FieldExtraction(
                    field_name="tax_treatment",
                    raw_text="TAX_INCLUSIVE_DERIVED",
                    normalized_value="INCLUSIVE",
                    method="DERIVED_ARITHMETIC",
                    verification_status="UNCERTAIN",
                    is_explicitly_present=False,
                )
                result.warnings.append("Net derived from gross minus tax (tax-inclusive assumption)")
        
        # Ensure invoice_number has a fallback
        if result.invoice_number is None:
            result.invoice_number = FieldExtraction(
                field_name="invoice_number",
                raw_text=None,
                normalized_value=None,
                method="NONE",
                verification_status="MISSING",
                is_explicitly_present=False,
            )
            result.warnings.append("Invoice number not found in document")
        
        return result
    
    except Exception as e:
        print(f"⚠ AI extraction failed ({provider}): {e}")
        return None
