"""Financial policy engine — deterministic and testable.

All money in integer cents (Decimal for calculations, int for storage).
Policy version: demo-policy-v1
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.models.purchase_order import PurchaseOrder
from app.models.invoice import Commitment


@dataclass
class RuleCheck:
    rule_id: str
    rule_name: str
    result: str  # PASS, FAIL, WARN, NOT_EVALUATED
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    explanation: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    severity: str = "ERROR"  # ERROR, WARNING, INFO


@dataclass
class PolicyEvaluation:
    decision: str = ""  # AUTO_APPROVED, NEEDS_REVIEW, NEEDS_INFORMATION, BLOCKED
    primary_reason_code: str = ""
    all_reason_codes: list[str] = field(default_factory=list)
    explanation: str = ""
    next_action: str = ""
    responsible_role: str = ""
    rules: list[RuleCheck] = field(default_factory=list)
    budget_before_cents: int = 0
    budget_after_cents: int = 0
    po_net_cents: int = 0
    allowed_overage_cents: int = 0
    allowed_ceiling_cents: int = 0
    committed_cents: int = 0
    projected_cents: int = 0


def _cents_to_dollars(cents: int) -> str:
    """Format cents as dollar display."""
    d = Decimal(cents) / Decimal(100)
    return f"${d:,.2f}"


def _calculate_overage(po_net_cents: int) -> int:
    """Calculate allowed overage: min(PO_net * 1%, $50.00), rounded half-up to cents."""
    pct = Decimal(po_net_cents) * Decimal(settings.po_overage_pct)
    max_overage = Decimal(settings.po_overage_max_cents)
    overage = min(pct, max_overage)
    # Round to whole cents, half-up
    overage = overage.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(overage)


def _get_committed_cents(db: Session, po_id: str, exclude_case_id: Optional[str] = None) -> int:
    """Get total active committed cents for a PO, optionally excluding a case."""
    query = db.query(func.coalesce(func.sum(Commitment.net_amount_cents), 0)).filter(
        Commitment.po_id == po_id,
        Commitment.status.in_(["RESERVED", "POSTED", "PAID"]),
    )
    if exclude_case_id:
        query = query.filter(Commitment.case_id != exclude_case_id)
    return int(query.scalar())


def evaluate_policy(
    db: Session,
    invoice_net_cents: Optional[int],
    invoice_gross_cents: Optional[int],
    invoice_tax_cents: Optional[int],
    invoice_subtotal_cents: Optional[int],
    invoice_currency: Optional[str],
    invoice_date_str: Optional[str],
    invoice_number: Optional[str],
    vendor_resolved: bool,
    vendor_active: bool,
    vendor_id: Optional[str],
    po_matched: bool,
    po_id: Optional[str],
    po_requires_reviewer: bool,
    duplicate_blocking: bool,
    duplicate_type: Optional[str],
    duplicate_reason: Optional[str],
    has_identity_collision: bool,
    has_suspected_duplicate: bool,
    business_date: date,
    case_id: Optional[str] = None,
    line_items: list[dict] = None,
) -> PolicyEvaluation:
    """Evaluate all financial policy rules against the invoice data.
    
    Precedence: BLOCKED > NEEDS_INFORMATION > NEEDS_REVIEW > AUTO_APPROVED
    """
    eval_result = PolicyEvaluation()
    rules = []
    reason_codes = []

    # ── Rule 1: Required Fields ──
    missing_fields = []
    if not invoice_number:
        missing_fields.append("invoice_number")
    if not invoice_net_cents and invoice_net_cents != 0:
        missing_fields.append("net_total")
    if not invoice_currency:
        missing_fields.append("currency")
    if not invoice_date_str:
        missing_fields.append("invoice_date")

    rules.append(RuleCheck(
        rule_id="REQUIRED_FIELDS",
        rule_name="Required Fields Present",
        result="FAIL" if missing_fields else "PASS",
        observed_value=", ".join(missing_fields) if missing_fields else "All present",
        expected_value="invoice_number, net_total, currency, invoice_date",
        explanation=f"Missing required fields: {', '.join(missing_fields)}" if missing_fields else "All required fields present",
        severity="ERROR" if missing_fields else "INFO",
    ))
    if missing_fields:
        reason_codes.append("MISSING_" + missing_fields[0].upper())

    # ── Rule 2: Currency ──
    if invoice_currency:
        is_usd = invoice_currency.upper() == "USD"
        rules.append(RuleCheck(
            rule_id="CURRENCY_CHECK",
            rule_name="Currency is USD",
            result="PASS" if is_usd else "FAIL",
            observed_value=invoice_currency,
            expected_value="USD",
            explanation=f"Currency {invoice_currency} is {'supported' if is_usd else 'not supported (USD only)'}",
            severity="ERROR" if not is_usd else "INFO",
        ))
        if not is_usd:
            reason_codes.append("UNSUPPORTED_CURRENCY")

    # ── Rule 3: Invoice Date ──
    if invoice_date_str:
        try:
            # Parse various date formats
            inv_date = _parse_date(invoice_date_str)
            is_future = inv_date > business_date if inv_date else False
            rules.append(RuleCheck(
                rule_id="DATE_CHECK",
                rule_name="Invoice Date Not Future",
                result="FAIL" if is_future else "PASS",
                observed_value=str(inv_date) if inv_date else invoice_date_str,
                expected_value=f"On or before {business_date}",
                explanation=f"Invoice date {'is in the future' if is_future else 'is valid'}",
                severity="ERROR" if is_future else "INFO",
            ))
            if is_future:
                reason_codes.append("FUTURE_INVOICE_DATE")
        except Exception:
            rules.append(RuleCheck(
                rule_id="DATE_CHECK",
                rule_name="Invoice Date Valid",
                result="WARN",
                observed_value=invoice_date_str,
                explanation="Could not parse invoice date",
                severity="WARNING",
            ))

    # ── Rule 4: Vendor Resolution ──
    rules.append(RuleCheck(
        rule_id="VENDOR_APPROVED",
        rule_name="Vendor is Approved and Active",
        result="PASS" if (vendor_resolved and vendor_active) else "FAIL",
        observed_value=f"Resolved: {vendor_resolved}, Active: {vendor_active}" + (f", ID: {vendor_id}" if vendor_id else ""),
        expected_value="Vendor resolved and active",
        explanation=(
            f"Vendor {vendor_id} is approved and active" if (vendor_resolved and vendor_active)
            else "Vendor could not be resolved to an approved active vendor"
        ),
        severity="ERROR" if not (vendor_resolved and vendor_active) else "INFO",
    ))
    if not vendor_resolved:
        reason_codes.append("VENDOR_NOT_FOUND")
    elif not vendor_active:
        reason_codes.append("VENDOR_INACTIVE")

    # ── Rule 5: Duplicate Check ──
    if duplicate_blocking:
        rules.append(RuleCheck(
            rule_id="DUPLICATE_CHECK",
            rule_name="No Blocking Duplicates",
            result="FAIL",
            observed_value=duplicate_type or "DUPLICATE",
            explanation=duplicate_reason or "Duplicate invoice detected",
            severity="ERROR",
        ))
        reason_codes.append("DUPLICATE_INVOICE")
    elif has_identity_collision:
        rules.append(RuleCheck(
            rule_id="DUPLICATE_CHECK",
            rule_name="No Identity Collisions",
            result="FAIL",
            observed_value="IDENTITY_COLLISION",
            explanation=duplicate_reason or "Same invoice identity with different amounts",
            severity="ERROR",
        ))
        reason_codes.append("INVOICE_IDENTITY_COLLISION")
    elif has_suspected_duplicate:
        rules.append(RuleCheck(
            rule_id="DUPLICATE_CHECK",
            rule_name="No Suspected Duplicates",
            result="WARN",
            observed_value="SUSPECTED",
            explanation=duplicate_reason or "Possible duplicate submission",
            severity="WARNING",
        ))
        reason_codes.append("SUSPECTED_DUPLICATE")
    else:
        rules.append(RuleCheck(
            rule_id="DUPLICATE_CHECK",
            rule_name="No Duplicates Detected",
            result="PASS",
            explanation="No duplicate or collision detected",
            severity="INFO",
        ))

    # ── Rule 6: PO Match ──
    rules.append(RuleCheck(
        rule_id="PO_MATCHED",
        rule_name="Purchase Order Matched",
        result="PASS" if (po_matched and not po_requires_reviewer) else "FAIL",
        observed_value=f"PO: {po_id}" if po_id else "No PO matched",
        explanation=(
            f"Matched to PO {po_id}" if po_matched
            else ("PO candidates found but absent reference requires reviewer selection" if po_requires_reviewer
                  else "No purchase order could be confirmed")
        ) + (" (reviewer selection required)" if po_requires_reviewer and not po_matched else ""),
        severity="ERROR" if not po_matched else ("WARNING" if po_requires_reviewer else "INFO"),
    ))
    if not po_matched and po_requires_reviewer:
        reason_codes.append("PO_AMBIGUOUS")
    elif not po_matched:
        reason_codes.append("PO_NOT_FOUND")

    # ── Rule 7: Arithmetic Reconciliation ──
    arithmetic_ok = True
    tolerance = settings.arithmetic_tolerance_cents  # 1 cent

    if invoice_subtotal_cents is not None and invoice_tax_cents is not None and invoice_gross_cents is not None:
        expected_gross = invoice_subtotal_cents + invoice_tax_cents
        diff = abs(expected_gross - invoice_gross_cents)
        arith_pass = diff <= tolerance
        rules.append(RuleCheck(
            rule_id="ARITHMETIC_GROSS",
            rule_name="Gross = Subtotal + Tax",
            result="PASS" if arith_pass else "FAIL",
            observed_value=f"Subtotal {_cents_to_dollars(invoice_subtotal_cents)} + Tax {_cents_to_dollars(invoice_tax_cents)} = {_cents_to_dollars(expected_gross)}",
            expected_value=f"Gross {_cents_to_dollars(invoice_gross_cents)} (tolerance: ${tolerance/100:.2f})",
            explanation=f"Arithmetic {'reconciles' if arith_pass else 'does not reconcile'} (diff: {_cents_to_dollars(diff)})",
            severity="ERROR" if not arith_pass else "INFO",
        ))
        if not arith_pass:
            arithmetic_ok = False
            reason_codes.append("ARITHMETIC_ERROR")

    # Check line items sum to subtotal
    if line_items and invoice_subtotal_cents is not None:
        line_sum = sum(item.get('amount_cents', 0) for item in line_items)
        if line_sum > 0:
            diff = abs(line_sum - invoice_subtotal_cents)
            lines_ok = diff <= tolerance
            rules.append(RuleCheck(
                rule_id="ARITHMETIC_LINES",
                rule_name="Line Items Sum to Subtotal",
                result="PASS" if lines_ok else "WARN",
                observed_value=f"Line sum: {_cents_to_dollars(line_sum)}",
                expected_value=f"Subtotal: {_cents_to_dollars(invoice_subtotal_cents)}",
                explanation=f"Line items {'reconcile' if lines_ok else 'do not reconcile'} with subtotal",
                severity="WARNING" if not lines_ok else "INFO",
            ))

    # ── Rule 8: PO Budget / Cumulative Exposure ──
    if po_matched and po_id and invoice_net_cents is not None:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if po:
            po_net = po.net_amount_cents
            overage = _calculate_overage(po_net)
            ceiling = po_net + overage
            committed = _get_committed_cents(db, po_id, exclude_case_id=case_id)
            projected = committed + invoice_net_cents
            within_budget = projected <= ceiling

            eval_result.po_net_cents = po_net
            eval_result.allowed_overage_cents = overage
            eval_result.allowed_ceiling_cents = ceiling
            eval_result.committed_cents = committed
            eval_result.projected_cents = projected
            eval_result.budget_before_cents = committed
            eval_result.budget_after_cents = projected

            # Check if within tolerance but over original PO
            near_limit = projected > po_net and within_budget

            rules.append(RuleCheck(
                rule_id="PO_BUDGET",
                rule_name="PO Cumulative Budget Check",
                result="PASS" if within_budget else "FAIL",
                observed_value=(
                    f"PO net: {_cents_to_dollars(po_net)}, "
                    f"Committed: {_cents_to_dollars(committed)}, "
                    f"This invoice: {_cents_to_dollars(invoice_net_cents)}, "
                    f"Projected: {_cents_to_dollars(projected)}"
                ),
                expected_value=(
                    f"Ceiling: {_cents_to_dollars(ceiling)} "
                    f"(PO {_cents_to_dollars(po_net)} + overage {_cents_to_dollars(overage)})"
                ),
                explanation=(
                    f"{'WITHIN' if within_budget else 'EXCEEDS'} budget. "
                    f"Projected cumulative net {_cents_to_dollars(projected)} "
                    f"{'<=' if within_budget else '>'} "
                    f"ceiling {_cents_to_dollars(ceiling)}"
                    + (f". Exceeds by {_cents_to_dollars(projected - ceiling)}." if not within_budget else "")
                    + (f" (within tolerance: {_cents_to_dollars(projected - po_net)} over PO net)" if near_limit else "")
                ),
                severity="ERROR" if not within_budget else ("WARNING" if near_limit else "INFO"),
            ))

            if not within_budget:
                reason_codes.append("PO_CUMULATIVE_LIMIT_EXCEEDED")
            elif near_limit:
                # Tolerance warning — passes but notable
                rules.append(RuleCheck(
                    rule_id="PO_TOLERANCE_WARNING",
                    rule_name="PO Tolerance Usage",
                    result="WARN",
                    observed_value=f"Using {_cents_to_dollars(projected - po_net)} of {_cents_to_dollars(overage)} overage allowance",
                    explanation=f"Invoice approved within tolerance but {_cents_to_dollars(projected - po_net)} over original PO net amount",
                    severity="WARNING",
                ))
    elif po_matched and invoice_net_cents is None:
        rules.append(RuleCheck(
            rule_id="PO_BUDGET",
            rule_name="PO Budget Check",
            result="NOT_EVALUATED",
            explanation="Cannot evaluate budget: invoice net amount unknown",
            severity="ERROR",
        ))
        reason_codes.append("MISSING_NET_TOTAL")

    # ── Determine Final Decision ──
    eval_result.rules = rules

    # Precedence: BLOCKED > NEEDS_INFORMATION > NEEDS_REVIEW > AUTO_APPROVED
    has_block = duplicate_blocking
    has_missing_info = any(rc.startswith("MISSING_") for rc in reason_codes)
    has_review = any(rc in (
        "VENDOR_NOT_FOUND", "VENDOR_INACTIVE", "PO_NOT_FOUND", "PO_AMBIGUOUS",
        "PO_CUMULATIVE_LIMIT_EXCEEDED", "INVOICE_IDENTITY_COLLISION",
        "FUTURE_INVOICE_DATE", "UNSUPPORTED_CURRENCY", "ARITHMETIC_ERROR",
        "SUSPECTED_DUPLICATE",
    ) for rc in reason_codes)

    if has_block:
        eval_result.decision = "BLOCKED"
        eval_result.primary_reason_code = "DUPLICATE_INVOICE"
        eval_result.explanation = _build_explanation("BLOCKED", reason_codes, rules)
        eval_result.next_action = "Review original approved invoice. No further action needed unless this is a dispute."
        eval_result.responsible_role = "AP Reviewer"
    elif has_missing_info:
        eval_result.decision = "NEEDS_INFORMATION"
        eval_result.primary_reason_code = reason_codes[0] if reason_codes else "MISSING_FIELDS"
        eval_result.explanation = _build_explanation("NEEDS_INFORMATION", reason_codes, rules)
        eval_result.next_action = "Request missing information from vendor and resubmit corrected document."
        eval_result.responsible_role = "AP Clerk / Vendor"
    elif has_review:
        eval_result.decision = "NEEDS_REVIEW"
        eval_result.primary_reason_code = reason_codes[0] if reason_codes else "REVIEW_REQUIRED"
        eval_result.explanation = _build_explanation("NEEDS_REVIEW", reason_codes, rules)
        eval_result.next_action = _build_next_action(reason_codes)
        eval_result.responsible_role = "AP Reviewer"
    else:
        eval_result.decision = "AUTO_APPROVED"
        eval_result.primary_reason_code = "ALL_CHECKS_PASSED"
        eval_result.explanation = _build_explanation("AUTO_APPROVED", reason_codes, rules)
        eval_result.next_action = "Approved for AP processing. No payment has been executed."
        eval_result.responsible_role = "System"

    eval_result.all_reason_codes = reason_codes
    return eval_result


def _parse_date(date_str: str) -> Optional[date]:
    """Parse common date formats."""
    import re
    from datetime import datetime

    # Try common formats
    formats = [
        "%B %d, %Y",       # March 10, 2026
        "%b %d, %Y",       # Mar 10, 2026
        "%Y-%m-%d",         # 2026-03-10
        "%m/%d/%Y",         # 03/10/2026
        "%d/%m/%Y",         # 10/03/2026
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _build_explanation(decision: str, reason_codes: list[str], rules: list[RuleCheck]) -> str:
    """Build a human-readable explanation from actual rule results."""
    if decision == "AUTO_APPROVED":
        return "All required checks passed. Approved for AP processing. No payment has been executed."

    parts = []
    for rule in rules:
        if rule.result in ("FAIL", "WARN") and rule.severity in ("ERROR", "WARNING"):
            parts.append(rule.explanation)

    if not parts:
        return f"Decision: {decision}"

    return f"{decision}: " + " | ".join(parts)


def _build_next_action(reason_codes: list[str]) -> str:
    """Build next-action guidance from reason codes."""
    actions = []
    if "PO_AMBIGUOUS" in reason_codes:
        actions.append("Select the correct PO and provide a reason.")
    if "PO_CUMULATIVE_LIMIT_EXCEEDED" in reason_codes:
        actions.append("Request PO amendment or obtain a corrected invoice.")
    if "VENDOR_NOT_FOUND" in reason_codes:
        actions.append("Verify vendor identity and add to approved vendor list if appropriate.")
    if "VENDOR_INACTIVE" in reason_codes:
        actions.append("Reactivate vendor or reject invoice.")
    if "INVOICE_IDENTITY_COLLISION" in reason_codes:
        actions.append("Determine if this is a legitimate correction or attempted duplicate.")
    if "FUTURE_INVOICE_DATE" in reason_codes:
        actions.append("Verify invoice date with vendor.")
    if "UNSUPPORTED_CURRENCY" in reason_codes:
        actions.append("Non-USD invoices are not supported in this system.")
    if "ARITHMETIC_ERROR" in reason_codes:
        actions.append("Verify invoice arithmetic with vendor.")
    return " ".join(actions) if actions else "Review flagged issues and take appropriate action."
