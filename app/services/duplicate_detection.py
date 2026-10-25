"""Duplicate detection: byte-level repeats and business-identity duplicates.

Distinct layers:
1. Byte-level: SHA-256 match → link to existing case
2. Business identity: vendor_id + normalized_invoice_number
   - Same identity + same amounts + active approval → BLOCKED
   - Same identity + different amounts → IDENTITY_COLLISION
   - Similar amount/date/vendor → suspected duplicate warning
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session
from app.models.invoice import InvoiceCase, SourceDocument, Commitment


@dataclass
class DuplicateCheckResult:
    is_byte_duplicate: bool = False
    is_business_duplicate: bool = False
    is_identity_collision: bool = False
    is_suspected_duplicate: bool = False
    duplicate_case_id: Optional[str] = None
    duplicate_type: Optional[str] = None  # BYTE_REPEAT, DUPLICATE_INVOICE, IDENTITY_COLLISION, SUSPECTED
    reason: Optional[str] = None
    blocking: bool = False
    original_decision: Optional[str] = None
    original_gross_cents: Optional[int] = None


def normalize_invoice_number(inv_num: Optional[str]) -> Optional[str]:
    """Conservative normalization: lowercase, strip whitespace, preserve leading zeros."""
    if not inv_num:
        return None
    cleaned = inv_num.strip().lower()
    # Normalize case and whitespace only
    cleaned = " ".join(cleaned.split())
    return cleaned


def aggressive_normalize(inv_num: Optional[str]) -> Optional[str]:
    """Aggressive normalization for suspicion (strip punctuation too)."""
    if not inv_num:
        return None
    cleaned = normalize_invoice_number(inv_num)
    # Strip all non-alphanumeric
    cleaned = re.sub(r'[^a-z0-9]', '', cleaned)
    return cleaned


def check_byte_duplicate(db: Session, sha256_hash: str) -> DuplicateCheckResult:
    """Check if identical bytes have been submitted before."""
    existing = db.query(SourceDocument).filter(
        SourceDocument.sha256_hash == sha256_hash
    ).first()

    if existing:
        return DuplicateCheckResult(
            is_byte_duplicate=True,
            duplicate_case_id=existing.case_id,
            duplicate_type="BYTE_REPEAT",
            reason=f"Identical file (SHA-256 match) already submitted in case {existing.case_id}",
        )

    return DuplicateCheckResult()


def check_business_duplicate(
    db: Session,
    vendor_id: Optional[str],
    invoice_number: Optional[str],
    currency: Optional[str],
    gross_cents: Optional[int],
    net_cents: Optional[int],
    current_case_id: Optional[str] = None,
) -> DuplicateCheckResult:
    """Check for business-level duplicates.
    
    Args:
        current_case_id: Exclude this case from duplicate checks (for re-evaluation)
    """
    result = DuplicateCheckResult()

    if not vendor_id or not invoice_number:
        return result

    norm_inv = normalize_invoice_number(invoice_number)
    if not norm_inv:
        return result

    # Find cases with same vendor + normalized invoice number
    query = db.query(InvoiceCase).filter(
        InvoiceCase.vendor_id == vendor_id,
        InvoiceCase.normalized_invoice_number == norm_inv,
    )
    if current_case_id:
        query = query.filter(InvoiceCase.id != current_case_id)

    existing_cases = query.all()

    for case in existing_cases:
        # Check if the existing case has an active approval
        has_active_commitment = db.query(Commitment).filter(
            Commitment.case_id == case.id,
            Commitment.status.in_(["RESERVED", "POSTED", "PAID"]),
        ).first() is not None

        if case.current_decision == "AUTO_APPROVED" or has_active_commitment:
            # Same amounts → BLOCKED as duplicate
            if (case.current_gross_cents == gross_cents and
                case.current_net_cents == net_cents and
                case.currency == currency):
                return DuplicateCheckResult(
                    is_business_duplicate=True,
                    duplicate_case_id=case.id,
                    duplicate_type="DUPLICATE_INVOICE",
                    reason=(
                        f"Invoice with same vendor ({vendor_id}), number ({invoice_number}), "
                        f"and amounts already approved in case {case.id}"
                    ),
                    blocking=True,
                    original_decision=case.current_decision,
                    original_gross_cents=case.current_gross_cents,
                )
            else:
                # Same identity, different amounts → collision
                return DuplicateCheckResult(
                    is_identity_collision=True,
                    duplicate_case_id=case.id,
                    duplicate_type="IDENTITY_COLLISION",
                    reason=(
                        f"Invoice with same vendor ({vendor_id}) and number ({invoice_number}) "
                        f"exists in case {case.id} but with different amounts. "
                        f"May be a correction or attempted duplicate."
                    ),
                    original_decision=case.current_decision,
                    original_gross_cents=case.current_gross_cents,
                )

        # Unresolved earlier submission — link for review
        if case.current_decision in (None, "NEEDS_REVIEW", "NEEDS_INFORMATION"):
            return DuplicateCheckResult(
                is_suspected_duplicate=True,
                duplicate_case_id=case.id,
                duplicate_type="SUSPECTED",
                reason=(
                    f"Earlier submission with same vendor/number exists in case {case.id} "
                    f"(status: {case.current_decision or 'processing'}). Review needed."
                ),
                original_decision=case.current_decision,
            )

    return result
