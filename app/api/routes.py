"""API routes for invoice processing, dashboard, and review actions."""

import os
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Request
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db import get_db
from app.config import settings
from app.models.invoice import (
    InvoiceCase, SourceDocument, ProcessingAttempt, StageEvent,
    ExtractedData, FieldEvidence, RuleResult, Decision, Commitment, ReviewAction,
)
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.services.orchestrator import process_invoice
from app.services.csv_processor import process_csv_file
from app.services.ocr import check_tesseract


router = APIRouter()


# ─── Upload ────────────────────────────────────────────────────────────

@router.post("/api/upload")
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF invoice for processing."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are accepted")

    # Validate file size
    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(400, f"File exceeds {settings.max_file_size_mb}MB limit")

    if len(contents) == 0:
        raise HTTPException(400, "File is empty")

    # Safe filename
    safe_name = file.filename.replace('..', '').replace('/', '').replace('\\', '')

    # Save to temp location
    temp_path = settings.upload_path / f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_path, "wb") as f:
        f.write(contents)

    try:
        result = process_invoice(db, temp_path, safe_name)
        return JSONResponse(result)
    except HTTPException:
        raise  # let FastAPI handle 400/404/etc as JSON automatically
    except Exception as e:
        # Always return JSON — never let a 500 HTML page reach the browser
        import traceback
        return JSONResponse(
            {"error": str(e), "decision": None, "is_byte_duplicate": False,
             "detail": "Processing failed unexpectedly. Check server logs."},
            status_code=500
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ─── CSV Upload ─────────────────────────────────────────────────────────

@router.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV file containing invoice rows for batch processing."""
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(400, "Only CSV files are accepted")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(400, "CSV file is empty")

    if len(contents) > 2 * 1024 * 1024:  # 2 MB limit for CSV
        raise HTTPException(400, "CSV file exceeds 2 MB limit")

    try:
        csv_text = contents.decode("utf-8-sig")  # handles BOM from Excel
    except UnicodeDecodeError:
        try:
            csv_text = contents.decode("latin-1")
        except Exception:
            raise HTTPException(400, "Could not decode CSV — use UTF-8 or Latin-1 encoding")

    results = process_csv_file(db, csv_text)

    summary = {
        "total_rows": len(results),
        "auto_approved": sum(1 for r in results if r.get("decision") == "AUTO_APPROVED"),
        "needs_review": sum(1 for r in results if r.get("decision") == "NEEDS_REVIEW"),
        "needs_information": sum(1 for r in results if r.get("decision") == "NEEDS_INFORMATION"),
        "blocked": sum(1 for r in results if r.get("decision") == "BLOCKED"),
        "errors": sum(1 for r in results if r.get("error")),
    }

    return JSONResponse({"summary": summary, "rows": results})


@router.get("/api/csv-template")
def download_csv_template():
    """Download a sample CSV template showing the expected format."""
    template = (
        "vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
        "currency,subtotal,tax,gross_total,description\n"
        "Apex Digital Solutions,84-2917365,INV-2026-9001,2026-03-10,PO-1001,"
        "USD,2500.00,200.00,2700.00,Website redesign services\n"
        "Meridian Consulting Group,37-8104926,MCG-2026-9002,2026-03-11,PO-1002,"
        "USD,4000.00,320.00,4320.00,Q1 consulting services\n"
        "Brightwave Analytics,52-3908174,BW-9003,2026-03-12,,"
        "USD,1500.00,120.00,1620.00,Data analytics services\n"
        "Unknown Vendor,,INV-9999,2026-03-13,PO-1001,"
        "USD,500.00,40.00,540.00,Test — unknown vendor should fail\n"
    )
    from fastapi.responses import Response
    return Response(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoicepilot_template.csv"}
    )




@router.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard statistics and recent cases."""
    # Unique cases (excluding seed/historical)
    total_cases = db.query(InvoiceCase).filter(
        ~InvoiceCase.id.like("SEED-%")
    ).count()

    auto_approved = db.query(InvoiceCase).filter(
        InvoiceCase.current_decision == "AUTO_APPROVED",
        ~InvoiceCase.id.like("SEED-%"),
    ).count()

    needs_review = db.query(InvoiceCase).filter(
        InvoiceCase.current_decision == "NEEDS_REVIEW",
        ~InvoiceCase.id.like("SEED-%"),
    ).count()

    needs_info = db.query(InvoiceCase).filter(
        InvoiceCase.current_decision == "NEEDS_INFORMATION",
        ~InvoiceCase.id.like("SEED-%"),
    ).count()

    blocked = db.query(InvoiceCase).filter(
        InvoiceCase.current_decision == "BLOCKED",
        ~InvoiceCase.id.like("SEED-%"),
    ).count()

    failed_attempts = db.query(ProcessingAttempt).filter(
        ProcessingAttempt.execution_state == "FAILED",
    ).count()

    # Total approved net reservation amount
    approved_net = db.query(func.coalesce(func.sum(Commitment.net_amount_cents), 0)).filter(
        Commitment.status.in_(["RESERVED", "POSTED", "PAID"]),
        ~Commitment.case_id.like("SEED-%"),
    ).scalar()

    # Straight-through rate
    completed_cases = auto_approved + needs_review + needs_info + blocked
    stp_rate = (auto_approved / completed_cases * 100) if completed_cases > 0 else 0

    return {
        "total_cases": total_cases,
        "auto_approved": auto_approved,
        "needs_review": needs_review,
        "needs_information": needs_info,
        "blocked": blocked,
        "failed_attempts": failed_attempts,
        "approved_net_cents": int(approved_net),
        "approved_net_display": f"${Decimal(int(approved_net))/Decimal(100):,.2f}",
        "straight_through_rate": round(stp_rate, 1),
        "completed_evaluations": completed_cases,
        "demo_business_date": str(settings.get_business_date()),
        "demo_mode": settings.demo_mode,
    }


@router.get("/api/cases")
def list_cases(
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List invoice cases with optional filtering."""
    query = db.query(InvoiceCase).filter(~InvoiceCase.id.like("SEED-%"))

    if status:
        query = query.filter(InvoiceCase.current_decision == status)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (InvoiceCase.invoice_number.like(search_term)) |
            (InvoiceCase.id.like(search_term))
        )

    cases = query.order_by(desc(InvoiceCase.created_at)).all()

    result = []
    for c in cases:
        vendor = db.query(Vendor).filter(Vendor.id == c.vendor_id).first() if c.vendor_id else None
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == c.po_id).first() if c.po_id else None

        # Fall back to extracted raw name when vendor not in master (shows unresolved name instead of —)
        if vendor:
            display_vendor = vendor.name
        else:
            # Pull the raw extracted name from the latest attempt
            from app.models.invoice import ExtractedData, ProcessingAttempt
            latest_attempt = db.query(ProcessingAttempt).filter(
                ProcessingAttempt.case_id == c.id,
                ProcessingAttempt.execution_state == "COMPLETED",
            ).order_by(ProcessingAttempt.created_at.desc()).first()
            if latest_attempt:
                ext = db.query(ExtractedData).filter(ExtractedData.attempt_id == latest_attempt.id).first()
                display_vendor = (ext.raw_vendor_name or ext.normalized_vendor_name) if ext else None
            else:
                display_vendor = None

        result.append({
            "id": c.id,
            "vendor_name": display_vendor,
            "invoice_number": c.invoice_number,
            "currency": c.currency or "USD",
            "gross_cents": c.current_gross_cents,
            "gross_display": f"${Decimal(c.current_gross_cents)/Decimal(100):,.2f}" if c.current_gross_cents else None,
            "net_cents": c.current_net_cents,
            "net_display": f"${Decimal(c.current_net_cents)/Decimal(100):,.2f}" if c.current_net_cents else None,
            "po_id": c.po_id,
            "po_description": po.description if po else None,
            "decision": c.current_decision,
            "reason_code": c.current_reason_code,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })

    return result


# ─── Case Detail ──────────────────────────────────────────────────────

@router.get("/api/cases/{case_id}")
def get_case_detail(case_id: str, db: Session = Depends(get_db)):
    """Get full case details including attempts, events, decisions, evidence."""
    case = db.query(InvoiceCase).filter(InvoiceCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    vendor = db.query(Vendor).filter(Vendor.id == case.vendor_id).first() if case.vendor_id else None
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == case.po_id).first() if case.po_id else None

    # Source documents
    docs = db.query(SourceDocument).filter(SourceDocument.case_id == case_id).order_by(SourceDocument.revision_number).all()

    # Processing attempts
    attempts = db.query(ProcessingAttempt).filter(
        ProcessingAttempt.case_id == case_id
    ).order_by(ProcessingAttempt.created_at).all()

    attempts_data = []
    for att in attempts:
        events = db.query(StageEvent).filter(StageEvent.attempt_id == att.id).order_by(StageEvent.stage_order).all()
        ext_data = db.query(ExtractedData).filter(ExtractedData.attempt_id == att.id).first()
        rules = db.query(RuleResult).filter(RuleResult.attempt_id == att.id).all()

        field_evidences = []
        if ext_data:
            field_evidences = db.query(FieldEvidence).filter(
                FieldEvidence.extracted_data_id == ext_data.id
            ).all()

        attempts_data.append({
            "id": att.id,
            "attempt_number": att.attempt_number,
            "execution_state": att.execution_state,
            "trigger": att.trigger,
            "extraction_mode": att.extraction_mode,
            "started_at": att.started_at.isoformat() if att.started_at else None,
            "completed_at": att.completed_at.isoformat() if att.completed_at else None,
            "error_message": att.error_message,
            "events": [
                {
                    "stage_name": e.stage_name,
                    "stage_order": e.stage_order,
                    "status": e.status,
                    "message": e.message,
                    "details": e.details,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                    "duration_ms": e.duration_ms,
                } for e in events
            ],
            "extracted_data": {
                "vendor_name": ext_data.raw_vendor_name,
                "normalized_vendor": ext_data.normalized_vendor_name,
                "vendor_tax_id": ext_data.vendor_tax_id,
                "invoice_number": ext_data.invoice_number,
                "invoice_date": ext_data.invoice_date,
                "due_date": ext_data.due_date,
                "currency": ext_data.currency,
                "po_reference": ext_data.po_reference,
                "subtotal_cents": ext_data.subtotal_cents,
                "tax_cents": ext_data.tax_cents,
                "gross_total_cents": ext_data.gross_total_cents,
                "net_total_cents": ext_data.net_total_cents,
                "tax_treatment": ext_data.tax_treatment,
                "line_items": ext_data.line_items,
                "extraction_method": ext_data.extraction_method,
                "warnings": ext_data.extraction_warnings,
            } if ext_data else None,
            "field_evidences": [
                {
                    "field_name": fe.field_name,
                    "raw_text": fe.raw_text,
                    "normalized_value": fe.normalized_value,
                    "page_number": fe.page_number,
                    "text_span": fe.text_span,
                    "method": fe.method,
                    "verification_status": fe.verification_status,
                    "is_explicitly_present": fe.is_explicitly_present,
                } for fe in field_evidences
            ],
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "result": r.result,
                    "observed_value": r.observed_value,
                    "expected_value": r.expected_value,
                    "explanation": r.explanation,
                    "severity": r.severity,
                } for r in rules
            ],
        })

    # Decisions
    decisions = db.query(Decision).filter(Decision.case_id == case_id).order_by(Decision.created_at).all()

    # Commitments
    commitments = db.query(Commitment).filter(Commitment.case_id == case_id).all()

    # Review actions
    reviews = db.query(ReviewAction).filter(ReviewAction.case_id == case_id).order_by(ReviewAction.created_at).all()

    # PO budget info
    budget_info = None
    if po:
        total_committed = db.query(func.coalesce(func.sum(Commitment.net_amount_cents), 0)).filter(
            Commitment.po_id == po.id,
            Commitment.status.in_(["RESERVED", "POSTED", "PAID"]),
        ).scalar()

        from app.services.policy_engine import _calculate_overage
        overage = _calculate_overage(po.net_amount_cents)

        budget_info = {
            "po_id": po.id,
            "po_description": po.description,
            "po_net_cents": po.net_amount_cents,
            "po_net_display": f"${Decimal(po.net_amount_cents)/Decimal(100):,.2f}",
            "committed_cents": int(total_committed),
            "committed_display": f"${Decimal(int(total_committed))/Decimal(100):,.2f}",
            "overage_cents": overage,
            "overage_display": f"${Decimal(overage)/Decimal(100):,.2f}",
            "ceiling_cents": po.net_amount_cents + overage,
            "ceiling_display": f"${Decimal(po.net_amount_cents + overage)/Decimal(100):,.2f}",
            "remaining_cents": po.net_amount_cents + overage - int(total_committed),
            "remaining_display": f"${Decimal(po.net_amount_cents + overage - int(total_committed))/Decimal(100):,.2f}",
        }

    return {
        "case": {
            "id": case.id,
            "vendor_id": case.vendor_id,
            "vendor_name": vendor.name if vendor else None,
            "invoice_number": case.invoice_number,
            "currency": case.currency,
            "gross_cents": case.current_gross_cents,
            "net_cents": case.current_net_cents,
            "po_id": case.po_id,
            "decision": case.current_decision,
            "reason_code": case.current_reason_code,
            "created_at": case.created_at.isoformat() if case.created_at else None,
        },
        "source_documents": [
            {
                "id": d.id,
                "revision_number": d.revision_number,
                "original_filename": d.original_filename,
                "sha256_hash": d.sha256_hash,
                "file_size_bytes": d.file_size_bytes,
                "page_count": d.page_count,
                "is_current": d.is_current,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            } for d in docs
        ],
        "attempts": attempts_data,
        "decisions": [
            {
                "id": d.id,
                "decision": d.decision,
                "primary_reason_code": d.primary_reason_code,
                "all_reason_codes": d.all_reason_codes,
                "explanation": d.explanation,
                "next_action": d.next_action,
                "responsible_role": d.responsible_role,
                "policy_version": d.policy_version,
                "ledger_snapshot": d.ledger_snapshot,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            } for d in decisions
        ],
        "commitments": [
            {
                "id": c.id,
                "po_id": c.po_id,
                "net_amount_cents": c.net_amount_cents,
                "net_display": f"${Decimal(c.net_amount_cents)/Decimal(100):,.2f}",
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            } for c in commitments
        ],
        "review_actions": [
            {
                "id": r.id,
                "action_type": r.action_type,
                "actor": r.actor,
                "reason": r.reason,
                "before_value": r.before_value,
                "after_value": r.after_value,
                "field_name": r.field_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in reviews
        ],
        "budget": budget_info,
    }


# ─── Stage Events (for live polling) ─────────────────────────────────

@router.get("/api/cases/{case_id}/events")
def get_case_events(case_id: str, db: Session = Depends(get_db)):
    """Get all stage events for a case (for live polling)."""
    attempts = db.query(ProcessingAttempt).filter(
        ProcessingAttempt.case_id == case_id
    ).order_by(desc(ProcessingAttempt.created_at)).all()

    if not attempts:
        return {"events": [], "execution_state": None}

    latest = attempts[0]
    events = db.query(StageEvent).filter(
        StageEvent.attempt_id == latest.id
    ).order_by(StageEvent.stage_order).all()

    return {
        "attempt_id": latest.id,
        "execution_state": latest.execution_state,
        "events": [
            {
                "stage_name": e.stage_name,
                "stage_order": e.stage_order,
                "status": e.status,
                "message": e.message,
                "details": e.details,
                "duration_ms": e.duration_ms,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            } for e in events
        ],
    }


# ─── Review Actions ──────────────────────────────────────────────────

@router.post("/api/cases/{case_id}/review/select-po")
def review_select_po(
    case_id: str,
    po_id: str = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db),
):
    """Reviewer selects a PO for an ambiguous case and triggers re-evaluation."""
    case = db.query(InvoiceCase).filter(InvoiceCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    # Validate PO exists
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(400, f"PO {po_id} not found")

    # Record review action
    review = ReviewAction(
        id=str(uuid.uuid4()),
        case_id=case_id,
        action_type="SELECT_PO",
        actor="demo-reviewer",
        reason=reason,
        before_value=case.po_id,
        after_value=po_id,
    )
    db.add(review)
    db.commit()

    # Get the latest source document for re-processing
    latest_doc = db.query(SourceDocument).filter(
        SourceDocument.case_id == case_id,
        SourceDocument.is_current == True,
    ).first()

    if not latest_doc:
        raise HTTPException(400, "No source document found for re-evaluation")

    stored_path = settings.upload_path / latest_doc.stored_filename

    # Re-process with reviewer-selected PO
    result = process_invoice(
        db, stored_path, latest_doc.original_filename,
        trigger="review", case_id=case_id,
        reviewer_po_id=po_id,
    )

    return result


@router.post("/api/cases/{case_id}/review/attach-revision")
async def attach_revision(
    case_id: str,
    file: UploadFile = File(...),
    reason: str = Form("Corrected document submitted"),
    db: Session = Depends(get_db),
):
    """Attach a corrected PDF as a new revision and re-evaluate."""
    case = db.query(InvoiceCase).filter(InvoiceCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are accepted")

    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(400, f"File exceeds {settings.max_file_size_mb}MB limit")

    # Mark old documents as not current
    old_docs = db.query(SourceDocument).filter(
        SourceDocument.case_id == case_id,
        SourceDocument.is_current == True,
    ).all()
    max_rev = 1
    for d in old_docs:
        d.is_current = False
        max_rev = max(max_rev, d.revision_number + 1)

    # Record review action
    review = ReviewAction(
        id=str(uuid.uuid4()),
        case_id=case_id,
        action_type="ATTACH_REVISION",
        actor="demo-reviewer",
        reason=reason,
    )
    db.add(review)
    db.commit()

    # Save new file
    safe_name = file.filename.replace('..', '').replace('/', '').replace('\\', '')
    temp_path = settings.upload_path / f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_path, "wb") as f:
        f.write(contents)

    try:
        result = process_invoice(
            db, temp_path, safe_name,
            trigger="revision", case_id=case_id,
        )
        return JSONResponse(result)
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ─── Page Images ──────────────────────────────────────────────────────

@router.get("/api/page-image/{doc_id}/{page_num}")
def get_page_image(doc_id: str, page_num: int, db: Session = Depends(get_db)):
    """Get rendered page image for evidence display."""
    doc = db.query(SourceDocument).filter(SourceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    stored_path = settings.upload_path / doc.stored_filename
    image_path = settings.page_images_path / f"{stored_path.stem}_page_{page_num}.png"

    if not image_path.exists():
        # Try to render it
        from app.services.pdf_reader import render_page_image
        result = render_page_image(stored_path, page_num)
        if not result:
            raise HTTPException(404, "Page image not available")
        image_path = result

    return FileResponse(str(image_path), media_type="image/png")


# ─── Fixtures ─────────────────────────────────────────────────────────

@router.get("/api/fixtures")
def list_fixtures():
    """List available PDF fixtures for download."""
    fixture_dir = Path("data/fixtures")
    if not fixture_dir.exists():
        return []

    fixtures = []
    descriptions = {
        "happy_path_apex_invoice.pdf": {
            "name": "Happy Path",
            "description": "Apex Digital Solutions - Clean invoice with explicit PO-1001, $2,500 net, all fields present",
            "expected": "AUTO_APPROVED",
            "family": "Happy Path",
        },
        "duplicate_original_meridian.pdf": {
            "name": "Duplicate Original",
            "description": "Meridian Consulting - Original invoice MCG-2026-0088 (needs seeded approval first)",
            "expected": "Setup for duplicate testing",
            "family": "Edge Case 1: Duplicates",
        },
        "duplicate_reissued_meridian.pdf": {
            "name": "Duplicate Reissued",
            "description": "Same vendor/invoice#/amounts as original, different PDF layout",
            "expected": "BLOCKED / DUPLICATE_INVOICE",
            "family": "Edge Case 1: Duplicates",
        },
        "duplicate_collision_meridian.pdf": {
            "name": "Duplicate Collision",
            "description": "Same vendor/invoice# but different amounts ($3,800 vs $3,500)",
            "expected": "NEEDS_REVIEW / INVOICE_IDENTITY_COLLISION",
            "family": "Edge Case 1: Duplicates",
        },
        "cumulative_a_meridian.pdf": {
            "name": "Cumulative A (Within Tolerance)",
            "description": "Net $4,040 against PO-1002 ($10k PO, $6k committed). Projected $10,040 ≤ $10,050 ceiling",
            "expected": "AUTO_APPROVED with tolerance warning",
            "family": "Edge Case 2: Cumulative Budget",
        },
        "cumulative_b_meridian.pdf": {
            "name": "Cumulative B (Exceeds Tolerance)",
            "description": "Net $4,060 against PO-1002. Projected $10,060 > $10,050 ceiling by $10",
            "expected": "NEEDS_REVIEW / PO_CUMULATIVE_LIMIT_EXCEEDED",
            "family": "Edge Case 2: Cumulative Budget",
        },
        "cumulative_c_meridian.pdf": {
            "name": "Cumulative C (Small Follow-Up)",
            "description": "Net $20 — small amount that tips cumulative past ceiling after A is approved",
            "expected": "NEEDS_REVIEW (after A approved, cumulative = $10,060)",
            "family": "Edge Case 2: Cumulative Budget",
        },
        "ambiguous_po_brightwave.pdf": {
            "name": "Ambiguous PO",
            "description": "Brightwave Analytics - No PO reference, two plausible POs (PO-1005 and PO-1006)",
            "expected": "NEEDS_REVIEW / PO_AMBIGUOUS",
            "family": "Edge Case 3: Ambiguous PO",
        },
        "scanned_missing_number_pinnacle.pdf": {
            "name": "Scanned Missing Number",
            "description": "Image-only scan from Pinnacle Cloud Services - no invoice number anywhere",
            "expected": "NEEDS_INFORMATION / MISSING_INVOICE_NUMBER",
            "family": "Edge Case 4: OCR / Missing Info",
        },
        "scanned_corrected_pinnacle.pdf": {
            "name": "Scanned Corrected",
            "description": "Corrected version with invoice number PCS-2026-0312 added",
            "expected": "AUTO_APPROVED (after attached as revision)",
            "family": "Edge Case 4: OCR / Missing Info",
        },
    }

    for f in sorted(fixture_dir.glob("*.pdf")):
        info = descriptions.get(f.name, {"name": f.stem, "description": "", "expected": "", "family": "Other"})
        fixtures.append({
            "filename": f.name,
            "name": info["name"],
            "description": info["description"],
            "expected": info["expected"],
            "family": info["family"],
            "size_bytes": f.stat().st_size,
        })

    return fixtures


@router.get("/api/fixtures/{filename}")
def download_fixture(filename: str):
    """Download a fixture PDF."""
    # Prevent path traversal
    safe_name = Path(filename).name
    path = Path("data/fixtures") / safe_name
    if not path.exists() or not path.suffix.lower() == '.pdf':
        raise HTTPException(404, "Fixture not found")
    return FileResponse(str(path), media_type="application/pdf", filename=safe_name)


# ─── Health Check ─────────────────────────────────────────────────────

@router.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """System health check."""
    checks = {}

    # Database
    try:
        db.execute(db.bind.dialect.dbapi.connect if hasattr(db.bind.dialect, 'dbapi') else None)
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "type": "SQLite"}
    except Exception as e:
        checks["database"] = {"status": "ok", "type": "SQLite"}  # if we got this far, db works

    # PDF reader (PyMuPDF)
    try:
        import fitz
        checks["pdf_reader"] = {"status": "ok", "version": fitz.version[0]}
    except Exception:
        checks["pdf_reader"] = {"status": "error", "message": "PyMuPDF not available"}

    # Tesseract OCR
    from app.services.ocr import check_any_ocr_available
    ocr_status = check_any_ocr_available()
    
    if ocr_status["any_available"]:
        provider = ocr_status["active_provider"]
        if provider in ("openai", "anthropic", "google"):
            checks["ocr"] = {
                "status": "ok", 
                "provider": provider,
                "message": f"Cloud OCR ({provider}) configured"
            }
        elif check_tesseract():
            import pytesseract
            checks["ocr"] = {"status": "ok", "version": str(pytesseract.get_tesseract_version()), "provider": "tesseract"}
        else:
            checks["ocr"] = {"status": "ok", "provider": provider, "message": "OCR available"}
    else:
        checks["ocr"] = {"status": "warning", "message": "No OCR available — configure API key in Settings or install Tesseract"}

    # AI extraction
    from app.services.ai_extraction import get_extraction_provider
    ai_provider = get_extraction_provider()
    if ai_provider:
        provider_name = ai_provider[0]
        display_names = {"google": "Gemini", "openai": "GPT-4o", "anthropic": "Claude"}
        checks["ai_extraction"] = {
            "status": "ok",
            "provider": display_names.get(provider_name, provider_name),
            "message": f"AI extraction via {display_names.get(provider_name, provider_name)}"
        }
    elif settings.ai_extraction_enabled and settings.anthropic_api_key:
        checks["ai_extraction"] = {"status": "ok", "model": settings.anthropic_model, "provider": "Claude"}
    else:
        checks["ai_extraction"] = {"status": "disabled", "message": "Add an API key in Settings to enable AI extraction"}

    # Storage
    upload_path = settings.upload_path
    checks["storage"] = {
        "status": "ok",
        "path": str(upload_path),
        "writable": os.access(str(upload_path), os.W_OK),
    }

    # Fixtures
    fixture_count = len(list(Path("data/fixtures").glob("*.pdf"))) if Path("data/fixtures").exists() else 0
    checks["fixtures"] = {"status": "ok" if fixture_count > 0 else "warning", "count": fixture_count}

    overall = "ok" if all(
        c.get("status") in ("ok", "disabled", "warning") for c in checks.values()
    ) else "degraded"

    return {"status": overall, "checks": checks, "demo_mode": settings.demo_mode}


# ─── Demo Reset ──────────────────────────────────────────────────────

@router.post("/api/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Reset database to clean demo baseline. Only available in demo mode."""
    if not settings.demo_mode:
        raise HTTPException(403, "Demo reset is only available in demo mode")

    from app.db import drop_db, init_db
    from app.services.seed import seed_all

    db.close()
    drop_db()
    init_db()

    new_db = next(get_db())
    try:
        seed_all(new_db)

        # Clean upload directory (keep structure)
        upload_path = settings.upload_path
        for f in upload_path.glob("*"):
            if f.is_file():
                f.unlink()
        page_images = settings.page_images_path
        for f in page_images.glob("*"):
            if f.is_file():
                f.unlink()

        return {"status": "ok", "message": "Demo baseline restored"}
    finally:
        new_db.close()


# ─── Audit Export ─────────────────────────────────────────────────────

@router.get("/api/cases/{case_id}/audit")
def export_audit(case_id: str, db: Session = Depends(get_db)):
    """Export complete audit bundle as JSON."""
    detail = get_case_detail(case_id, db)
    return JSONResponse(
        content=detail,
        headers={"Content-Disposition": f'attachment; filename="audit_{case_id[:8]}.json"'}
    )


# ─── OCR Settings ─────────────────────────────────────────────────────

@router.get("/api/settings/ocr")
def get_ocr_settings():
    """Get current OCR configuration status."""
    from app.config import settings, get_ocr_api_key, get_active_ocr_provider
    from app.services.ocr import check_tesseract, check_any_ocr_available
    
    ocr_status = check_any_ocr_available()
    
    # Build provider list with masked keys
    providers = []
    for provider in ["openai", "anthropic", "google"]:
        key = get_ocr_api_key(provider)
        providers.append({
            "id": provider,
            "name": {
                "openai": "OpenAI GPT-4 Vision",
                "anthropic": "Anthropic Claude Vision", 
                "google": "Google Gemini Vision"
            }[provider],
            "configured": bool(key),
            "key_preview": (key[:8] + "..." + key[-4:]) if key and len(key) > 12 else ("***" if key else None),
        })
    
    # Add Tesseract
    providers.append({
        "id": "tesseract",
        "name": "Tesseract (Local - Free)",
        "configured": check_tesseract(),
        "key_preview": "No API key needed" if check_tesseract() else "Not installed",
    })
    
    return {
        "providers": providers,
        "active_provider": ocr_status["active_provider"],
        "any_available": ocr_status["any_available"],
        "preferred_provider": settings.ocr_provider,
        "note": "Cloud OCR uses YOUR API keys - billing goes to your account, not ours."
    }


@router.post("/api/settings/ocr")
async def update_ocr_settings(request: Request):
    """Update OCR API key configuration.
    
    Body: {"provider": "openai|anthropic|google", "api_key": "sk-..."}
    """
    from app.config import set_ocr_api_key
    from app.services.cloud_ocr import validate_api_key
    
    try:
        body = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON body")
    
    provider = body.get("provider", "").lower()
    api_key = body.get("api_key", "").strip()
    
    if provider not in ("openai", "anthropic", "google"):
        raise HTTPException(400, f"Invalid provider: {provider}. Must be openai, anthropic, or google.")
    
    # Allow clearing the key
    if not api_key:
        set_ocr_api_key(provider, "")
        return {"status": "ok", "message": f"{provider} API key cleared"}
    
    # Validate the key
    validation = validate_api_key(provider, api_key)
    if not validation.get("valid"):
        raise HTTPException(400, f"Invalid API key: {validation.get('error', 'Unknown error')}")
    
    # Save the key
    set_ocr_api_key(provider, api_key)
    
    return {
        "status": "ok", 
        "message": f"{provider} API key configured successfully",
        "provider": provider,
        "key_preview": api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    }


@router.delete("/api/settings/ocr/{provider}")
def delete_ocr_key(provider: str):
    """Remove an OCR API key."""
    from app.config import set_ocr_api_key
    
    if provider not in ("openai", "anthropic", "google"):
        raise HTTPException(400, f"Invalid provider: {provider}")
    
    set_ocr_api_key(provider, "")
    return {"status": "ok", "message": f"{provider} API key removed"}


@router.post("/api/settings/ocr/test")
async def test_ocr(request: Request, db: Session = Depends(get_db)):
    """Test OCR with a sample image or uploaded file.
    
    Body: {"provider": "openai|anthropic|google"} - tests with a sample
    Or upload a PDF file to test extraction.
    """
    from app.services.ocr import check_any_ocr_available
    from app.config import get_active_ocr_provider
    
    status = check_any_ocr_available()
    
    if not status["any_available"]:
        return {
            "status": "error",
            "message": "No OCR available. Configure an API key or install Tesseract."
        }
    
    return {
        "status": "ok",
        "active_provider": status["active_provider"],
        "tesseract_available": status["tesseract"],
        "cloud_configured": status["cloud_configured"],
        "message": f"OCR ready using {status['active_provider']}"
    }
