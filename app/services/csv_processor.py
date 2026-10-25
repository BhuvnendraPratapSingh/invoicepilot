"""
CSV invoice processor — accepts structured invoice rows and runs them
through the same vendor resolution, PO matching, and policy pipeline
as PDF invoices. Skips PDF reading and field extraction stages.

Supported CSV columns:
  vendor_name       - Vendor display name (matched against vendor master)
  vendor_tax_id     - EIN/Tax ID (preferred over name for matching)
  invoice_number    - Required unique invoice identifier
  invoice_date      - Date in YYYY-MM-DD or Month DD, YYYY format
  po_reference      - Optional PO number (e.g. PO-1001)
  currency          - Defaults to USD
  subtotal          - Net/subtotal amount in dollars (e.g. 2500.00)
  tax               - Tax amount in dollars (optional)
  gross_total       - Total due in dollars (required if subtotal missing)
  description       - Optional service description
"""

import csv
import uuid
import io
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models.invoice import (
    InvoiceCase, ProcessingAttempt, StageEvent,
    ExtractedData, FieldEvidence, RuleResult, Decision, Commitment, ReviewAction,
)
from app.services.vendor_resolution import resolve_vendor
from app.services.duplicate_detection import check_business_duplicate, normalize_invoice_number
from app.services.po_matching import match_po
from app.services.policy_engine import evaluate_policy


def _utcnow():
    return datetime.now(timezone.utc)


def _parse_cents(value: Optional[str]) -> Optional[int]:
    """Parse a dollar string like '2500.00' or '2,500' into integer cents."""
    if not value or not value.strip():
        return None
    cleaned = value.strip().replace('$', '').replace(',', '')
    try:
        d = Decimal(cleaned)
        return int(d * 100)
    except (InvalidOperation, ValueError):
        return None


def _record(db, attempt_id, stage_name, stage_order, status, message=None, details=None, started_at=None):
    now = _utcnow()
    duration_ms = int((now - started_at).total_seconds() * 1000) if started_at else None
    ev = StageEvent(
        id=str(uuid.uuid4()),
        attempt_id=attempt_id,
        stage_name=stage_name,
        stage_order=stage_order,
        status=status,
        message=message,
        details=details,
        started_at=started_at or now,
        completed_at=now if status != "STARTED" else None,
        duration_ms=duration_ms,
    )
    db.add(ev)
    db.flush()


CSV_STAGES = [
    ("receive_csv_row", "Receive & Validate CSV Row"),
    ("field_validation", "Field Validation"),
    ("vendor_resolution", "Vendor Resolution"),
    ("duplicate_detection", "Business Duplicate Detection"),
    ("po_matching", "PO Matching"),
    ("policy_evaluation", "Financial Policy Evaluation"),
    ("commit_decision", "Commit Decision"),
    ("publish_results", "Publish Results"),
]


def process_csv_row(db: Session, row: dict, row_number: int) -> dict:
    """
    Process a single CSV invoice row through the full business logic pipeline.
    Returns the same shape as process_invoice() from orchestrator.py.
    """
    attempt_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    now = _utcnow()

    # ── Create case and attempt ──
    case = InvoiceCase(id=case_id)
    db.add(case)

    attempt = ProcessingAttempt(
        id=attempt_id,
        case_id=case_id,
        source_document_id="csv_row",
        execution_state="RUNNING",
        trigger="csv_upload",
        extraction_mode="csv",
        started_at=now,
    )
    db.add(attempt)
    db.flush()

    # ═══════════════════════
    # Stage 1: Validate row
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "receive_csv_row", 0, "STARTED", started_at=stage_start)

    errors = []
    if not row.get("invoice_number", "").strip():
        errors.append("invoice_number is required")
    if not row.get("vendor_name", "").strip() and not row.get("vendor_tax_id", "").strip():
        errors.append("either vendor_name or vendor_tax_id is required")

    subtotal_cents = _parse_cents(row.get("subtotal") or row.get("net_amount"))
    tax_cents = _parse_cents(row.get("tax") or row.get("tax_amount"))
    gross_cents = _parse_cents(row.get("gross_total") or row.get("total") or row.get("amount_due"))

    if subtotal_cents is None and gross_cents is None:
        errors.append("subtotal or gross_total is required")

    if errors:
        _record(db, attempt_id, "receive_csv_row", 0, "FAILED",
                message="Row validation failed: " + "; ".join(errors), started_at=stage_start)
        for i in range(1, len(CSV_STAGES)):
            _record(db, attempt_id, CSV_STAGES[i][0], i, "SKIPPED",
                    message="Skipped: row validation failed")
        attempt.execution_state = "FAILED"
        attempt.error_message = "; ".join(errors)
        attempt.completed_at = _utcnow()
        db.commit()
        return {"case_id": case_id, "attempt_id": attempt_id, "decision": None,
                "error": "; ".join(errors), "row_number": row_number, "is_byte_duplicate": False}

    _record(db, attempt_id, "receive_csv_row", 0, "COMPLETED",
            message=f"Row {row_number} valid: invoice={row.get('invoice_number','').strip()}",
            started_at=stage_start)
    db.commit()

    # Derive net
    if subtotal_cents is not None:
        net_cents = subtotal_cents
    elif gross_cents is not None and tax_cents is not None:
        net_cents = gross_cents - tax_cents
    else:
        net_cents = gross_cents

    # ═══════════════════════
    # Stage 2: Field validation
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "field_validation", 1, "STARTED", started_at=stage_start)

    invoice_number = row.get("invoice_number", "").strip()
    invoice_date = row.get("invoice_date", "").strip() or None
    currency = (row.get("currency", "") or "USD").strip().upper()
    po_reference = row.get("po_reference", "").strip() or None
    description = row.get("description", "").strip() or None

    missing = []
    if not invoice_date:
        missing.append("invoice_date")
    if currency != "USD":
        missing.append("unsupported_currency")

    _record(db, attempt_id, "field_validation", 1, "COMPLETED",
            message="All fields valid" if not missing else f"Issues: {', '.join(missing)}",
            started_at=stage_start)

    # Store extracted data (from CSV, not PDF)
    ext_data = ExtractedData(
        id=str(uuid.uuid4()),
        attempt_id=attempt_id,
        raw_vendor_name=row.get("vendor_name", "").strip() or None,
        normalized_vendor_name=row.get("vendor_name", "").strip() or None,
        vendor_tax_id=row.get("vendor_tax_id", "").strip() or None,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        po_reference=po_reference,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        gross_total_cents=gross_cents,
        net_total_cents=net_cents,
        tax_treatment="EXCLUSIVE" if (subtotal_cents and tax_cents) else None,
        line_items=[{"description": description, "amount_cents": net_cents}] if description else [],
        extraction_method="csv",
        extraction_warnings=missing if missing else None,
        document_hash=None,
        page_texts={"1": f"[CSV Row {row_number}] " + str(row)},
    )
    db.add(ext_data)
    db.flush()
    db.commit()

    # ═══════════════════════
    # Stage 3: Vendor resolution
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "vendor_resolution", 2, "STARTED", started_at=stage_start)

    vendor_result = resolve_vendor(
        db,
        extracted_name=ext_data.normalized_vendor_name,
        extracted_tax_id=ext_data.vendor_tax_id,
    )

    if vendor_result.resolved:
        case.vendor_id = vendor_result.vendor_id

    _record(db, attempt_id, "vendor_resolution", 2, "COMPLETED",
            message=f"Vendor {'resolved: ' + vendor_result.vendor_name if vendor_result.resolved else 'not resolved: ' + (vendor_result.reason or '')}",
            details={"resolved": vendor_result.resolved, "vendor_id": vendor_result.vendor_id},
            started_at=stage_start)
    db.commit()

    # ═══════════════════════
    # Stage 4: Duplicate detection
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "duplicate_detection", 3, "STARTED", started_at=stage_start)

    dup_result = check_business_duplicate(
        db,
        vendor_id=vendor_result.vendor_id,
        invoice_number=invoice_number,
        currency=currency,
        gross_cents=gross_cents,
        net_cents=net_cents,
        current_case_id=case_id,
    )

    case.invoice_number = invoice_number
    case.normalized_invoice_number = normalize_invoice_number(invoice_number)
    case.currency = currency

    _record(db, attempt_id, "duplicate_detection", 3, "COMPLETED",
            message=dup_result.reason or "No duplicates detected",
            details={"is_duplicate": dup_result.is_business_duplicate, "is_collision": dup_result.is_identity_collision},
            started_at=stage_start)
    db.commit()

    # ═══════════════════════
    # Stage 5: PO matching
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "po_matching", 4, "STARTED", started_at=stage_start)

    po_result = None
    if vendor_result.resolved:
        po_result = match_po(
            db,
            vendor_id=vendor_result.vendor_id,
            po_reference=po_reference,
            invoice_currency=currency,
            invoice_description=description,
            invoice_net_cents=net_cents,
        )
        if po_result.matched:
            case.po_id = po_result.po_id

        _record(db, attempt_id, "po_matching", 4, "COMPLETED",
                message=f"PO {'matched: ' + po_result.po_id if po_result.matched else 'not matched: ' + (po_result.reason or '')}",
                details={"matched": po_result.matched, "po_id": po_result.po_id, "candidates": len(po_result.candidates)},
                started_at=stage_start)
    else:
        _record(db, attempt_id, "po_matching", 4, "SKIPPED",
                message="Vendor not resolved — PO matching skipped", started_at=stage_start)
    db.commit()

    # ═══════════════════════
    # Stage 6: Policy evaluation
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "policy_evaluation", 5, "STARTED", started_at=stage_start)

    policy_eval = evaluate_policy(
        db=db,
        invoice_net_cents=net_cents,
        invoice_gross_cents=gross_cents,
        invoice_tax_cents=tax_cents,
        invoice_subtotal_cents=subtotal_cents,
        invoice_currency=currency,
        invoice_date_str=invoice_date,
        invoice_number=invoice_number,
        vendor_resolved=vendor_result.resolved,
        vendor_active=vendor_result.is_active,
        vendor_id=vendor_result.vendor_id,
        po_matched=po_result.matched if po_result else False,
        po_id=po_result.po_id if po_result else None,
        po_requires_reviewer=po_result.requires_reviewer if po_result else True,
        duplicate_blocking=dup_result.blocking,
        duplicate_type=dup_result.duplicate_type,
        duplicate_reason=dup_result.reason,
        has_identity_collision=dup_result.is_identity_collision,
        has_suspected_duplicate=dup_result.is_suspected_duplicate,
        business_date=settings.get_business_date(),
        case_id=case_id,
        line_items=ext_data.line_items,
    )

    for rule in policy_eval.rules:
        rr = RuleResult(
            id=str(uuid.uuid4()),
            attempt_id=attempt_id,
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            result=rule.result,
            observed_value=rule.observed_value,
            expected_value=rule.expected_value,
            explanation=rule.explanation,
            evidence_refs=rule.evidence_refs,
            severity=rule.severity,
        )
        db.add(rr)

    _record(db, attempt_id, "policy_evaluation", 5, "COMPLETED",
            message=f"Decision: {policy_eval.decision} — {policy_eval.primary_reason_code}",
            details={"decision": policy_eval.decision, "reason_codes": policy_eval.all_reason_codes},
            started_at=stage_start)
    db.commit()

    # ═══════════════════════
    # Stage 7: Commit decision
    # ═══════════════════════
    stage_start = _utcnow()
    _record(db, attempt_id, "commit_decision", 6, "STARTED", started_at=stage_start)

    decision = Decision(
        id=str(uuid.uuid4()),
        case_id=case_id,
        attempt_id=attempt_id,
        decision=policy_eval.decision,
        primary_reason_code=policy_eval.primary_reason_code,
        all_reason_codes=policy_eval.all_reason_codes,
        explanation=policy_eval.explanation,
        next_action=policy_eval.next_action,
        responsible_role=policy_eval.responsible_role,
        policy_version=settings.policy_version,
        policy_snapshot={"version": settings.policy_version, "currency": settings.currency,
                         "arithmetic_tolerance_cents": settings.arithmetic_tolerance_cents,
                         "po_overage_pct": settings.po_overage_pct,
                         "po_overage_max_cents": settings.po_overage_max_cents},
        vendor_snapshot={"vendor_id": vendor_result.vendor_id, "vendor_name": vendor_result.vendor_name,
                         "match_method": vendor_result.match_method} if vendor_result.resolved else None,
        po_snapshot={"po_id": po_result.po_id} if po_result and po_result.matched else None,
        ledger_snapshot={"po_net_cents": policy_eval.po_net_cents,
                         "committed_cents": policy_eval.committed_cents,
                         "projected_cents": policy_eval.projected_cents,
                         "allowed_ceiling_cents": policy_eval.allowed_ceiling_cents} if policy_eval.po_net_cents else None,
    )
    db.add(decision)
    db.flush()

    commitment = None
    if policy_eval.decision == "AUTO_APPROVED" and po_result and po_result.po_id and net_cents is not None:
        commitment = Commitment(
            id=str(uuid.uuid4()),
            case_id=case_id,
            po_id=po_result.po_id,
            net_amount_cents=net_cents,
            status="RESERVED",
            decision_id=decision.id,
        )
        db.add(commitment)

    case.current_decision = policy_eval.decision
    case.current_reason_code = policy_eval.primary_reason_code
    case.current_gross_cents = gross_cents
    case.current_net_cents = net_cents

    attempt.execution_state = "COMPLETED"
    attempt.completed_at = _utcnow()

    _record(db, attempt_id, "commit_decision", 6, "COMPLETED",
            message=f"Decision committed: {policy_eval.decision}",
            details={"has_reservation": commitment is not None},
            started_at=stage_start)

    # Stage 8: Publish
    _record(db, attempt_id, "publish_results", 7, "COMPLETED", message="Results published")
    db.commit()

    return {
        "case_id": case_id,
        "attempt_id": attempt_id,
        "decision": policy_eval.decision,
        "primary_reason_code": policy_eval.primary_reason_code,
        "explanation": policy_eval.explanation,
        "next_action": policy_eval.next_action,
        "row_number": row_number,
        "invoice_number": invoice_number,
        "is_byte_duplicate": False,
        "po_candidates": [
            {"po_id": c.po_id, "description": c.description, "remaining_cents": c.remaining_cents}
            for c in (po_result.candidates if po_result else [])
        ],
    }


def process_csv_file(db: Session, csv_content: str) -> list[dict]:
    """Parse CSV content and process each row. Returns list of per-row results."""
    reader = csv.DictReader(io.StringIO(csv_content.strip()))

    # Normalize headers: lowercase + strip
    rows = []
    for raw_row in reader:
        row = {k.strip().lower().replace(' ', '_'): v for k, v in raw_row.items()}
        rows.append(row)

    if not rows:
        return [{"error": "CSV file is empty or has no data rows", "row_number": 0}]

    results = []
    for i, row in enumerate(rows, start=1):
        result = process_csv_row(db, row, row_number=i)
        results.append(result)

    return results
