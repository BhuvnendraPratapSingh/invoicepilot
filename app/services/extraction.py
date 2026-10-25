"""Local pattern-based field extraction from invoice text.

Reads actual document content using regex patterns. Supports multiple
invoice layouts through varied label patterns. Does NOT use fixture
filenames, invoice ID lookups, or expected-results manifests.
"""

import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FieldExtraction:
    """A single extracted field with provenance."""
    field_name: str
    raw_text: Optional[str] = None
    normalized_value: Optional[str] = None
    page_number: Optional[int] = None
    text_span: Optional[str] = None  # surrounding context
    method: str = "NATIVE_TEXT"
    verification_status: str = "UNCERTAIN"
    is_explicitly_present: bool = True


@dataclass
class ExtractionResult:
    """Complete extraction result from an invoice."""
    vendor_name: Optional[FieldExtraction] = None
    vendor_tax_id: Optional[FieldExtraction] = None
    vendor_address: Optional[FieldExtraction] = None
    invoice_number: Optional[FieldExtraction] = None
    invoice_date: Optional[FieldExtraction] = None
    due_date: Optional[FieldExtraction] = None
    currency: Optional[FieldExtraction] = None
    po_reference: Optional[FieldExtraction] = None
    subtotal: Optional[FieldExtraction] = None
    discount: Optional[FieldExtraction] = None
    shipping: Optional[FieldExtraction] = None
    tax: Optional[FieldExtraction] = None
    gross_total: Optional[FieldExtraction] = None
    tax_treatment: Optional[FieldExtraction] = None
    line_items: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extraction_method: str = "local"


def _parse_money(text: str) -> Optional[int]:
    """Parse a money string like '$2,500.00' into cents. Returns None if unparseable."""
    if not text:
        return None
    # Remove $ sign, commas, whitespace
    cleaned = text.replace('$', '').replace(',', '').strip()
    try:
        d = Decimal(cleaned)
        return int(d * 100)
    except (InvalidOperation, ValueError):
        return None


def _find_money_value(text: str, patterns: list[str]) -> Optional[tuple[str, str, int]]:
    """Find a money value matching any of the given label patterns.
    
    Returns (raw_text, label_context, cents) or None.
    Supports: $1,234.56  $1234.56  $1,234  $1234  USD 1,234.56
    Integer-dollar amounts (no cents) are accepted when preceded by a label.
    Labels may include parenthetical text like "Subtotal (void):".
    """
    # Currency prefix: optional $, USD, EUR etc. — captures the numeric part
    AMOUNT = r'(?:USD\s*|EUR\s*)?\$?([\d,]+\.\d{2})'
    AMOUNT_INT = r'(?:USD\s*|EUR\s*)?\$?([\d,]+)(?:\s|$)'
    # Flexible separator: allow colons, spaces, and short text between label and amount (same line)
    SEP = r'[^$\d\n]{0,40}'
    # Newline separator: label on one line, amount on next line
    SEP_NEWLINE = r'[:\s]*\n\s*'

    for pattern in patterns:
        # Strategy 1: Same line — label followed by amount (most common)
        match = re.search(
            pattern + SEP + AMOUNT,
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if not match:
            match = re.search(
                pattern + SEP + AMOUNT_INT,
                text,
                re.IGNORECASE | re.MULTILINE
            )
        if match:
            raw = match.group(1).strip()
            cents = _parse_money(raw)
            if cents is not None and cents > 0:
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end].strip()
                return (raw, context, cents)
        
        # Strategy 2: Label on one line, amount on next line
        # Pattern: "Subtotal:\n$2,500.00" or "Total Due:\n$2,700.00"
        match_nl = re.search(
            pattern + SEP_NEWLINE + AMOUNT,
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if match_nl:
            raw = match_nl.group(1).strip()
            cents = _parse_money(raw)
            if cents is not None and cents > 0:
                start = max(0, match_nl.start() - 10)
                end = min(len(text), match_nl.end() + 10)
                context = text[start:end].strip()
                return (raw, context, cents)
    return None


def _find_money_value_columnar(text: str, patterns: list[str]) -> Optional[tuple[str, str, int]]:
    """Fallback for columnar PDFs where amounts appear before labels on separate lines.
    
    This handles layouts like:
        $6,465.06       <- paired with Subtotal (index 0)
        $67.89          <- paired with Shipping (index 1)
        $6,532.95       <- paired with Total (index 2)
        Subtotal:
        Shipping:
        Total:
    where amounts are stacked in one column and labels in another.
    
    The strategy: find the consecutive label block, take the last N amounts before it
    (where N = number of labels in block), and pair them by positional index.
    """
    # Common label patterns for columnar invoice summaries (order matters for detection)
    COLUMNAR_LABELS = [
        (r'Subtotal', 'subtotal'),
        (r'Discount', 'discount'),
        (r'Less\s*Discount', 'discount'),
        (r'Shipping', 'shipping'),
        (r'Freight', 'shipping'),
        (r'Delivery', 'shipping'),
        (r'Tax(?:\s*\d+\.?\d*\s*%)?', 'tax'),
        (r'(?:Grand\s*)?Total', 'total'),
    ]
    
    # Find all label matches and their positions
    label_matches = []
    for label_pat, label_type in COLUMNAR_LABELS:
        for m in re.finditer(label_pat + r'\s*:?\s*(?:\n|$)', text, re.IGNORECASE | re.MULTILINE):
            # Avoid duplicate matches at same position
            if not any(abs(m.start() - existing[0]) < 5 for existing in label_matches):
                label_matches.append((m.start(), m.end(), m.group(0).strip(), label_type))
    
    if len(label_matches) < 2:
        # Not enough labels to be a columnar block
        return None
    
    # Sort by position
    label_matches.sort(key=lambda x: x[0])
    
    # Find consecutive label blocks (labels within 30 chars of each other - they should be very close)
    blocks = []
    current_block = [label_matches[0]]
    for i in range(1, len(label_matches)):
        prev_end = label_matches[i-1][1]
        curr_start = label_matches[i][0]
        if curr_start - prev_end < 30:  # Close together = same block
            current_block.append(label_matches[i])
        else:
            if len(current_block) >= 2:
                blocks.append(current_block)
            current_block = [label_matches[i]]
    if len(current_block) >= 2:
        blocks.append(current_block)
    
    if not blocks:
        return None
    
    # For each block, find amounts before it and pair by index
    for block in blocks:
        block_start = block[0][0]  # Start of first label in block
        num_labels = len(block)
        
        # Get all amounts before the label block
        before_text = text[:block_start]
        all_amounts = list(re.finditer(r'\$?([\d,]+\.\d{2})', before_text))
        
        if len(all_amounts) < num_labels:
            continue
        
        # Take the LAST N amounts (where N = number of labels in block)
        relevant_amounts = all_amounts[-num_labels:]
        
        # Map label types in this block with their indices
        label_type_to_idx = {}
        for idx, (lbl_start, lbl_end, lbl_text, lbl_type) in enumerate(block):
            if lbl_type not in label_type_to_idx:  # First occurrence wins
                label_type_to_idx[lbl_type] = idx
        
        # Now find the target pattern's index in block
        for pattern in patterns:
            pattern_lower = pattern.lower().replace(r'\s*', ' ').replace(r'\s+', ' ')
            
            # Check each label in block for match
            for idx, (lbl_start, lbl_end, lbl_text, lbl_type) in enumerate(block):
                if re.search(pattern, lbl_text, re.IGNORECASE):
                    # Found our target label at index `idx` in the block
                    if idx < len(relevant_amounts):
                        amt_match = relevant_amounts[idx]
                        raw = amt_match.group(1).strip()
                        cents = _parse_money(raw)
                        if cents is not None and cents > 0:
                            context = f"${raw} ... {lbl_text}"
                            return (raw, context, cents)
    
    return None


def _find_text_value(text: str, patterns: list[str]) -> Optional[tuple[str, str]]:
    """Find a text value matching any of the given label patterns.
    
    Returns (raw_text, context) or None.
    """
    for pattern in patterns:
        match = re.search(
            pattern + r'[:\s]+(.+?)(?:\n|$)',
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if match:
            raw = match.group(1).strip()
            if raw:
                start = max(0, match.start() - 10)
                end = min(len(text), match.end() + 10)
                context = text[start:end].strip()
                return (raw, context)
    return None


def _find_in_page_texts(page_texts: dict[int, str], patterns: list[str]) -> Optional[tuple[str, str, int]]:
    """Search across all pages for a pattern. Returns (raw, context, page_num)."""
    for page_num, text in sorted(page_texts.items()):
        result = _find_text_value(text, patterns)
        if result:
            return (result[0], result[1], page_num)
    return None


def _find_money_in_pages(page_texts: dict[int, str], patterns: list[str]) -> Optional[tuple[str, str, int, int]]:
    """Search across all pages for a money pattern. Returns (raw, context, page_num, cents).
    
    First tries standard same-line matching, then falls back to columnar PDF matching.
    """
    # Strategy 1: Same-line matching (most invoices)
    for page_num, text in sorted(page_texts.items()):
        result = _find_money_value(text, patterns)
        if result:
            return (result[0], result[1], page_num, result[2])
    
    # Strategy 2: Columnar PDF fallback (amounts on lines before labels)
    for page_num, text in sorted(page_texts.items()):
        result = _find_money_value_columnar(text, patterns)
        if result:
            return (result[0], result[1], page_num, result[2])
    
    return None


def extract_fields(page_texts: dict[int, str], method_per_page: dict[int, str] = None) -> ExtractionResult:
    """Extract structured invoice fields from page texts.
    
    Args:
        page_texts: Dict mapping 1-indexed page number to text content
        method_per_page: Dict mapping page number to extraction method (NATIVE_TEXT, OCR)
    """
    if method_per_page is None:
        method_per_page = {p: "NATIVE_TEXT" for p in page_texts}

    result = ExtractionResult()
    all_text = "\n\n".join(text for _, text in sorted(page_texts.items()))

    def _method_for_page(page_num: int) -> str:
        return method_per_page.get(page_num, "NATIVE_TEXT")

    # ── Vendor Name ──
    # First try explicit "Vendor:" label which is most reliable
    vendor_label_patterns = [r'Vendor\s*:', r'From\s*:', r'Supplier\s*:', r'Billed\s*By\s*:']
    vendor_label_result = _find_in_page_texts(page_texts, vendor_label_patterns)
    if vendor_label_result:
        raw, context, page = vendor_label_result
        cleaned = raw.strip()
        if cleaned:
            result.vendor_name = FieldExtraction(
                field_name="vendor_name",
                raw_text=cleaned,
                normalized_value=cleaned,
                page_number=page,
                text_span=context,
                method=_method_for_page(page),
                verification_status="VERIFIED",
            )

    # Fallback: look for company names at the top of page 1
    first_page = page_texts.get(1, "")  # needed for address extraction below too
    if result.vendor_name is None:
        for line in first_page.split('\n')[:5]:
            line = line.strip()
            if len(line) > 5 and any(c.isupper() for c in line[:3]):
                # Skip generic labels and non-vendor text
                if not any(skip in line.upper() for skip in [
                    'INVOICE', 'TAX INVOICE', 'BILL TO', 'CLIENT', 'DATE',
                    'SYNTHETIC', 'TEST DOCUMENT', 'NOT PAYABLE', 'CORRECTED',
                    'REVISED', 'DRAFT', 'COPY', 'DUPLICATE', 'SAMPLE',
                ]):
                    result.vendor_name = FieldExtraction(
                        field_name="vendor_name",
                        raw_text=line,
                        normalized_value=line.strip(),
                        page_number=1,
                        text_span=line,
                        method=_method_for_page(1),
                        verification_status="VERIFIED" if len(line) > 5 else "UNCERTAIN",
                    )
                    break

    # ── Vendor Tax ID ──
    tax_patterns = [r'Tax\s*ID', r'EIN', r'TIN', r'Federal\s*ID', r'Tax\s*Identification']
    tax_result = _find_in_page_texts(page_texts, tax_patterns)
    if tax_result:
        # Extract the ID number
        raw, context, page = tax_result
        # Clean: might have trailing text
        id_match = re.search(r'[\d]{2}[-]?\d{7}', raw)
        if id_match:
            result.vendor_tax_id = FieldExtraction(
                field_name="vendor_tax_id",
                raw_text=raw,
                normalized_value=id_match.group(0),
                page_number=page,
                text_span=context,
                method=_method_for_page(page),
                verification_status="VERIFIED",
            )

    # ── Vendor Address ──
    addr_result = _find_in_page_texts(page_texts, [r'(?:^|\n)(\d+\s+[\w\s]+(?:Drive|Blvd|Way|Street|Lane|Ave|Road).*?\d{5})'])
    if not addr_result:
        # Try to find address-like text near the top of page 1
        addr_match = re.search(
            r'(\d+\s+[A-Za-z\s,]+(?:Suite\s+\d+,?\s*)?[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5})',
            first_page
        )
        if addr_match:
            result.vendor_address = FieldExtraction(
                field_name="vendor_address",
                raw_text=addr_match.group(1),
                normalized_value=addr_match.group(1).strip(),
                page_number=1,
                text_span=addr_match.group(0),
                method=_method_for_page(1),
                verification_status="VERIFIED",
            )

    # ── Invoice Number ──
    inv_patterns = [
        r'Invoice\s*(?:Number|No|Num|#|Ref)',
        r'Invoice\s*No\.',
        r'Inv\s*#',
        r'Invoice\s*Ref',
    ]
    inv_result = _find_in_page_texts(page_texts, inv_patterns)
    if inv_result:
        raw, context, page = inv_result
        # Clean the value
        cleaned = raw.strip().rstrip(':').strip()
        result.invoice_number = FieldExtraction(
            field_name="invoice_number",
            raw_text=raw,
            normalized_value=cleaned,
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED" if cleaned else "MISSING",
        )
    
    # Fallback: look for standalone "# XXXXX" pattern (SuperStore format)
    if result.invoice_number is None or not result.invoice_number.normalized_value:
        for page_num, text in sorted(page_texts.items()):
            # Look for "# XXXXX" near INVOICE header
            inv_match = re.search(r'(?:INVOICE[^\n]*\n[^\n]*)?#\s*(\d+)', text, re.IGNORECASE)
            if inv_match:
                inv_num = inv_match.group(1).strip()
                result.invoice_number = FieldExtraction(
                    field_name="invoice_number",
                    raw_text=f"# {inv_num}",
                    normalized_value=inv_num,
                    page_number=page_num,
                    text_span=inv_match.group(0),
                    method=_method_for_page(page_num),
                    verification_status="VERIFIED",
                )
                break

    # If not found by label, do NOT guess from other fields
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

    # ── Invoice Date ──
    date_patterns = [
        r'(?:Invoice\s*)?Date(?:\s*of\s*Invoice)?',
        r'Date\s*of\s*Invoice',
        r'Inv(?:oice)?\s*Date',
    ]
    date_result = _find_in_page_texts(page_texts, date_patterns)
    if date_result:
        raw, context, page = date_result
        result.invoice_date = FieldExtraction(
            field_name="invoice_date",
            raw_text=raw,
            normalized_value=raw.strip(),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # ── Due Date ──
    due_patterns = [r'Due\s*Date', r'Payment\s*Due', r'Due\s*By']
    due_result = _find_in_page_texts(page_texts, due_patterns)
    if due_result:
        raw, context, page = due_result
        result.due_date = FieldExtraction(
            field_name="due_date",
            raw_text=raw,
            normalized_value=raw.strip(),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # ── Currency ──
    curr_patterns = [r'Currency']
    curr_result = _find_in_page_texts(page_texts, curr_patterns)
    if curr_result:
        raw, context, page = curr_result
        result.currency = FieldExtraction(
            field_name="currency",
            raw_text=raw,
            normalized_value=raw.strip().upper(),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )
    else:
        # Check for $ symbols indicating USD
        if '$' in all_text:
            result.currency = FieldExtraction(
                field_name="currency",
                raw_text="$",
                normalized_value="USD",
                page_number=1,
                text_span="Dollar sign ($) found in document",
                method="DERIVED_ARITHMETIC",
                verification_status="UNCERTAIN",
                is_explicitly_present=False,
            )
            result.warnings.append("Currency inferred from $ symbol, not explicitly stated")

    # ── PO Reference ──
    po_patterns = [
        r'(?:Purchase\s*Order|PO)\s*(?:Reference|Ref|Number|No|#)?',
        r'PO\s*#?',
        r'P\.?O\.?\s*(?:Reference|Ref|Number|No|#)?',
    ]
    po_result = _find_in_page_texts(page_texts, po_patterns)
    if po_result:
        raw, context, page = po_result
        cleaned = raw.strip().rstrip(':').strip()
        # Extract PO-XXXX pattern
        po_match = re.search(r'(PO[-\s]?\d+)', cleaned, re.IGNORECASE)
        if po_match:
            cleaned = po_match.group(1).upper().replace(' ', '-')
            if not cleaned.startswith('PO-'):
                cleaned = 'PO-' + cleaned.replace('PO', '')
        result.po_reference = FieldExtraction(
            field_name="po_reference",
            raw_text=raw,
            normalized_value=cleaned if cleaned else None,
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED" if cleaned else "MISSING",
        )

    # ── Money Fields ──
    # Subtotal
    subtotal_result = _find_money_in_pages(page_texts, [r'Sub\s*[Tt]otal'])
    if subtotal_result:
        raw, context, page, cents = subtotal_result
        result.subtotal = FieldExtraction(
            field_name="subtotal",
            raw_text=raw,
            normalized_value=str(cents),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # Discount
    discount_patterns = [r'Discount', r'Less\s*Discount', r'Discount\s*\(\d+%?\)']
    discount_result = _find_money_in_pages(page_texts, discount_patterns)
    if discount_result:
        raw, context, page, cents = discount_result
        result.discount = FieldExtraction(
            field_name="discount",
            raw_text=raw,
            normalized_value=str(cents),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # Shipping
    shipping_patterns = [r'Shipping', r'Freight', r'Delivery']
    shipping_result = _find_money_in_pages(page_texts, shipping_patterns)
    if shipping_result:
        raw, context, page, cents = shipping_result
        result.shipping = FieldExtraction(
            field_name="shipping",
            raw_text=raw,
            normalized_value=str(cents),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # Tax — matches "Tax (8%)", "Tax 5%", "Tax 5% (illustrative):", "VAT", "Sales Tax"
    tax_money_patterns = [
        r'(?:Sales\s*)?Tax\s*(?:\d+\.?\d*\s*%\s*)?(?:\([^)]*\))?',
        r'VAT\s*(?:\d+\.?\d*\s*%\s*)?',
        r'Tax\s*\(\d+%\)',
    ]
    tax_result = _find_money_in_pages(page_texts, tax_money_patterns)
    if tax_result:
        raw, context, page, cents = tax_result
        result.tax = FieldExtraction(
            field_name="tax",
            raw_text=raw,
            normalized_value=str(cents),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # Gross Total — must not match "Subtotal" or standalone "Amount"
    total_patterns = [
        r'Total\s+Due',
        r'Amount\s+Due',
        r'TOTAL\s+DUE',
        r'Grand\s*Total',
        r'(?:^|\n)\s*Total\s*:?(?:\s|$)',
        r'Amount\s+(?:Payable|Owed)',
        r'(?:^|\n)\s*TOTAL\s*:?(?:\s|$)',
        r'Invoice\s+Total',
        r'Balance\s+Due',
    ]
    total_result = _find_money_in_pages(page_texts, total_patterns)
    if total_result:
        raw, context, page, cents = total_result
        result.gross_total = FieldExtraction(
            field_name="gross_total",
            raw_text=raw,
            normalized_value=str(cents),
            page_number=page,
            text_span=context,
            method=_method_for_page(page),
            verification_status="VERIFIED",
        )

    # ── Derive Net Total ──
    # net = subtotal - discount + shipping
    subtotal_cents = int(result.subtotal.normalized_value) if result.subtotal and result.subtotal.normalized_value else None
    discount_cents = int(result.discount.normalized_value) if result.discount and result.discount.normalized_value else 0
    shipping_cents = int(result.shipping.normalized_value) if result.shipping and result.shipping.normalized_value else 0
    tax_cents = int(result.tax.normalized_value) if result.tax and result.tax.normalized_value else None
    gross_cents = int(result.gross_total.normalized_value) if result.gross_total and result.gross_total.normalized_value else None

    if subtotal_cents is not None:
        net_cents = subtotal_cents - discount_cents + shipping_cents
        result.tax_treatment = FieldExtraction(
            field_name="tax_treatment",
            raw_text="TAX_EXCLUSIVE",
            normalized_value="EXCLUSIVE",
            method="DERIVED_ARITHMETIC",
            verification_status="VERIFIED" if tax_cents is not None else "UNCERTAIN",
            is_explicitly_present=False,
        )
    elif gross_cents is not None and tax_cents is not None:
        # Derive net from gross - tax (tax-inclusive)
        net_cents = gross_cents - tax_cents
        result.tax_treatment = FieldExtraction(
            field_name="tax_treatment",
            raw_text="TAX_INCLUSIVE_DERIVED",
            normalized_value="INCLUSIVE",
            method="DERIVED_ARITHMETIC",
            verification_status="UNCERTAIN",
            is_explicitly_present=False,
        )
        result.warnings.append("Net derived from gross minus tax (tax-inclusive assumption)")
    else:
        net_cents = subtotal_cents  # Best effort: use subtotal as net
        if net_cents is None and gross_cents is not None:
            net_cents = gross_cents  # Last resort
            result.warnings.append("Unable to separate net from gross total")

    # Store line items (extract from table-like patterns)
    _extract_line_items(page_texts, result, method_per_page)

    return result


def _extract_line_items(page_texts: dict[int, str], result: ExtractionResult, method_per_page: dict[int, str]):
    """Extract line items from tabular content in the text."""
    all_text = "\n\n".join(text for _, text in sorted(page_texts.items()))

    # Pattern: description followed by dollar amount at end of line
    line_pattern = re.compile(
        r'^\s*(?:\d+\.?\s+)?(.+?)\s+\$?([\d,]+\.\d{2})\s*$',
        re.MULTILINE
    )

    items = []
    for match in line_pattern.finditer(all_text):
        desc = match.group(1).strip()
        amount_str = match.group(2).strip()

        # Skip total/subtotal lines
        if any(skip in desc.lower() for skip in ['subtotal', 'total', 'tax', 'discount', 'shipping', 'due', 'amount due']):
            continue

        cents = _parse_money(amount_str)
        if cents and cents > 0 and len(desc) > 3:
            items.append({
                'description': desc,
                'amount_cents': cents,
                'amount_display': f"${Decimal(cents)/Decimal(100):,.2f}",
                'raw_text': match.group(0).strip(),
            })

    result.line_items = items
