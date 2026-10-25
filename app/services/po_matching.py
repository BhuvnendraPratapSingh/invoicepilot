"""Purchase order matching and candidate ranking.

Rules:
- Explicit PO ref must exist, belong to vendor, match currency, and be open
- No PO ref: search eligible POs for vendor, show candidates
- Ambiguous/multiple candidates → NEEDS_REVIEW
- Absent PO ref always requires reviewer selection
"""

from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session
from app.models.purchase_order import PurchaseOrder
from app.models.invoice import Commitment


@dataclass
class POCandidate:
    po_id: str
    description: str
    service_scope: Optional[str]
    net_amount_cents: int
    committed_cents: int
    remaining_cents: int
    currency: str
    status: str
    match_reason: str  # EXPLICIT_REF, SERVICE_MATCH, AMOUNT_PROXIMITY
    rank: int = 0


@dataclass
class POMatchResult:
    matched: bool = False
    po_id: Optional[str] = None
    match_method: Optional[str] = None
    candidates: list[POCandidate] = field(default_factory=list)
    reason: Optional[str] = None
    requires_reviewer: bool = False


def _get_committed_cents(db: Session, po_id: str) -> int:
    """Get total active committed cents for a PO."""
    from sqlalchemy import func
    result = db.query(func.coalesce(func.sum(Commitment.net_amount_cents), 0)).filter(
        Commitment.po_id == po_id,
        Commitment.status.in_(["RESERVED", "POSTED", "PAID"]),
    ).scalar()
    return int(result)


def _make_candidate(db: Session, po: PurchaseOrder, match_reason: str) -> POCandidate:
    """Create a PO candidate with current capacity info."""
    committed = _get_committed_cents(db, po.id)
    return POCandidate(
        po_id=po.id,
        description=po.description or "",
        service_scope=po.service_scope,
        net_amount_cents=po.net_amount_cents,
        committed_cents=committed,
        remaining_cents=po.net_amount_cents - committed,
        currency=po.currency,
        status=po.status,
        match_reason=match_reason,
    )


def match_po(
    db: Session,
    vendor_id: str,
    po_reference: Optional[str],
    invoice_currency: str,
    invoice_description: Optional[str] = None,
    invoice_net_cents: Optional[int] = None,
) -> POMatchResult:
    """Match invoice to a purchase order."""

    result = POMatchResult()

    # 1. Explicit PO reference
    if po_reference:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_reference).first()

        if not po:
            result.reason = f"PO reference '{po_reference}' does not exist"
            result.requires_reviewer = True
            return result

        if po.vendor_id != vendor_id:
            result.reason = f"PO '{po_reference}' belongs to vendor {po.vendor_id}, not {vendor_id}"
            result.requires_reviewer = True
            return result

        if po.currency != invoice_currency:
            result.reason = f"PO currency {po.currency} does not match invoice currency {invoice_currency}"
            result.requires_reviewer = True
            return result

        if po.status not in ("OPEN", "APPROVED"):
            result.reason = f"PO '{po_reference}' has status {po.status}, not eligible"
            result.requires_reviewer = True
            return result

        candidate = _make_candidate(db, po, "EXPLICIT_REF")
        result.candidates.append(candidate)
        result.matched = True
        result.po_id = po.id
        result.match_method = "EXPLICIT_REF"
        return result

    # 2. No PO reference — search for eligible POs
    eligible_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.vendor_id == vendor_id,
        PurchaseOrder.currency == invoice_currency,
        PurchaseOrder.status.in_(["OPEN", "APPROVED"]),
    ).all()

    if not eligible_pos:
        result.reason = f"No eligible open POs found for vendor {vendor_id} in {invoice_currency}"
        result.requires_reviewer = True
        return result

    # Build candidates with ranking
    for po in eligible_pos:
        # Check description overlap
        match_reason = "SERVICE_MATCH"
        if invoice_description and po.service_scope:
            overlap = _text_overlap(invoice_description, po.service_scope)
            if overlap > 0.3:
                match_reason = "SERVICE_MATCH"
            else:
                match_reason = "AMOUNT_PROXIMITY"

        candidate = _make_candidate(db, po, match_reason)
        result.candidates.append(candidate)

    # Rank candidates
    for i, c in enumerate(sorted(result.candidates, key=lambda x: x.remaining_cents, reverse=True)):
        c.rank = i + 1

    if len(result.candidates) == 1:
        # Single candidate, but absent PO ref always requires reviewer
        result.reason = "Single eligible PO found, but absent PO reference requires reviewer selection"
        result.requires_reviewer = True
    else:
        result.reason = f"{len(result.candidates)} eligible POs found. Absent PO reference requires reviewer selection"
        result.requires_reviewer = True

    return result


def _text_overlap(a: str, b: str) -> float:
    """Word overlap between two text descriptions."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    common = words_a & words_b
    # Remove stop words
    stop = {'the', 'and', 'for', 'of', 'in', 'to', 'a', 'an', 'is', 'at', 'by', 'on', 'or'}
    common = common - stop
    meaningful_a = words_a - stop
    meaningful_b = words_b - stop
    if not meaningful_a or not meaningful_b:
        return 0.0
    return len(common) / max(len(meaningful_a), len(meaningful_b))
