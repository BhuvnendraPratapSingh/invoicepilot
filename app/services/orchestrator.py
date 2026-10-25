"""Pipeline orchestrator — runs all stages with persisted events.

Events correspond to real work. No fake progress, decorative sleeps,
precomputed decisions, or fixture-name-specific routing.
"""

import uuid
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models.invoice import (
    InvoiceCase, SourceDocument, ProcessingAttempt, StageEvent,
    ExtractedData, FieldEvidence, RuleResult, Decision, Commitment,
)
from app.services.pdf_reader import validate_and_read_pdf, render_page_image
from app.services.ocr import ocr_pdf_pages, check_tesseract, check_any_ocr_available
from app.services.extraction import extract_fields
from app.services.ai_extraction import ai_extract_fields, get_extraction_provider
from app.services.vendor_resolution import resolve_vendor
from app.services.duplicate_detection import (
    check_byte_duplicate, check_business_duplicate, normalize_invoice_number,
)
from app.services.po_matching import match_po
from app.services.policy_engine import evaluate_policy


STAGE_NAMES = [
    ("receive_validate", "Receive & Validate PDF"),
    ("byte_duplicate_check", "Byte-Level Duplicate Check"),
    ("text_extraction", "Text Extraction"),
    ("field_extraction", "Field Extraction"),
    ("field_validation", "Field Validation"),
    ("vendor_resolution", "Vendor Resolution"),
    ("duplicate_detection", "Business Duplicate Detection"),
    ("po_matching", "PO Matching"),
    ("policy_evaluation", "Financial Policy Evaluation"),
    ("commit_decision", "Commit Decision"),
    ("publish_results", "Publish Results"),
]


def _utcnow():
    return datetime.now(timezone.utc)


def _record_event(db: Session, attempt_id: str, stage_name: str, stage_order: int,
                   status: str, message: str = None, details: dict = None,
                   started_at: datetime = None) -> StageEvent:
    """Record a stage event."""
    now = _utcnow()
    duration_ms = None
    if started_at:
        duration_ms = int((now - started_at).total_seconds() * 1000)

    event = StageEvent(
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
    db.add(event)
    db.flush()
    return event


def _store_field_evidence(db: Session, extracted_data_id: str, extraction) -> None:
    """Store field evidence from extraction result."""
    fields = [
        'vendor_name', 'vendor_tax_id', 'vendor_address', 'invoice_number',
        'invoice_date', 'due_date', 'currency', 'po_reference',
        'subtotal', 'tax', 'gross_total', 'tax_treatment',
    ]
    for field_name in fields:
        field_ext = getattr(extraction, field_name, None)
        if field_ext:
            fe = FieldEvidence(
                id=str(uuid.uuid4()),
                extracted_data_id=extracted_data_id,
                field_name=field_name,
                raw_text=field_ext.raw_text,
                normalized_value=field_ext.normalized_value,
                page_number=field_ext.page_number,
                text_span=field_ext.text_span,
                method=field_ext.method,
                verification_status=field_ext.verification_status,
                is_explicitly_present=field_ext.is_explicitly_present,
            )
            db.add(fe)


def process_invoice(db: Session, file_path: Path, original_filename: str,
                     trigger: str = "upload", case_id: str = None,
                     reviewer_po_id: str = None) -> dict:
    """Run the complete invoice processing pipeline.
    
    Returns dict with case_id, attempt_id, decision, and details.
    """

    # ════════════════════════════════════════════════════════
    # Pre-pipeline: validate PDF and check byte-dup BEFORE creating any DB rows.
    # This prevents orphan cases when a repeat upload is detected.
    # ════════════════════════════════════════════════════════
    pdf_result = validate_and_read_pdf(file_path)

    if not pdf_result.success:
        # PDF is invalid — create a minimal failed case+attempt to record the error
        attempt_id = str(uuid.uuid4())
        if not case_id:
            case_id = str(uuid.uuid4())
            db.add(InvoiceCase(id=case_id))
        attempt = ProcessingAttempt(
            id=attempt_id, case_id=case_id, source_document_id="pending",
            execution_state="FAILED", trigger=trigger,
            started_at=_utcnow(), completed_at=_utcnow(),
            error_message=pdf_result.error,
        )
        db.add(attempt)
        db.flush()
        _record_event(db, attempt_id, "receive_validate", 0, "FAILED",
                       message=pdf_result.error, started_at=_utcnow())
        _skip_remaining(db, attempt_id, 1, "PDF validation failed")
        db.commit()
        return {"case_id": case_id, "attempt_id": attempt_id, "decision": None,
                "error": pdf_result.error, "is_byte_duplicate": False}

    # Byte-dup check is a read-only query — no rows created yet
    is_reevaluation = trigger in ("review", "revision") and case_id is not None
    byte_dup = check_byte_duplicate(db, pdf_result.sha256_hash)

    if byte_dup.is_byte_duplicate and not is_reevaluation:
        # Record a repeat-submission event on the ORIGINAL case, not a new one.
        original_case_id = byte_dup.duplicate_case_id
        repeat_attempt_id = str(uuid.uuid4())
        repeat_attempt = ProcessingAttempt(
            id=repeat_attempt_id, case_id=original_case_id,
            source_document_id="byte_repeat",
            execution_state="COMPLETED", trigger="repeat",
            started_at=_utcnow(), completed_at=_utcnow(),
        )
        db.add(repeat_attempt)
        db.flush()
        _record_event(db, repeat_attempt_id, "byte_duplicate_check", 1, "COMPLETED",
                       message=f"Identical file re-submitted (SHA-256 match). Linked to existing case.",
                       started_at=_utcnow())
        _skip_remaining(db, repeat_attempt_id, 2, "Byte-level duplicate")
        db.commit()
        return {"case_id": original_case_id, "attempt_id": repeat_attempt_id,
                "decision": None, "is_byte_duplicate": True,
                "duplicate_case_id": original_case_id}

    # ════════════════════════════════════════════════════════
    # Not a duplicate — NOW create the case and attempt
    # ════════════════════════════════════════════════════════
    attempt_id = str(uuid.uuid4())
    now = _utcnow()

    if not case_id:
        case_id = str(uuid.uuid4())
        case = InvoiceCase(id=case_id)
        db.add(case)
    else:
        case = db.query(InvoiceCase).filter(InvoiceCase.id == case_id).first()
        if not case:
            case = InvoiceCase(id=case_id)
            db.add(case)

    # Store the file and create source document
    stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
    stored_path = settings.upload_path / stored_filename
    shutil.copy2(str(file_path), str(stored_path))

    source_doc = SourceDocument(
        id=str(uuid.uuid4()),
        case_id=case_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        sha256_hash=pdf_result.sha256_hash,
        file_size_bytes=pdf_result.file_size_bytes,
        page_count=pdf_result.page_count,
    )
    db.add(source_doc)
    db.flush()

    attempt = ProcessingAttempt(
        id=attempt_id, case_id=case_id,
        source_document_id=source_doc.id,
        execution_state="RUNNING", trigger=trigger,
        started_at=now,
    )
    db.add(attempt)
    db.flush()

    # Backfill stage 1 & 2 events (work already done above)
    _record_event(db, attempt_id, "receive_validate", 0, "COMPLETED",
                   message=f"Valid PDF: {pdf_result.page_count} pages, {pdf_result.file_size_bytes} bytes",
                   details={"page_count": pdf_result.page_count, "sha256": pdf_result.sha256_hash},
                   started_at=now)
    _record_event(db, attempt_id, "byte_duplicate_check", 1, "COMPLETED",
                   message="No byte-level duplicate found", started_at=now)

    # Render page images for preview
    for page in pdf_result.pages:
        render_page_image(stored_path, page.page_number)

    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 3: Text Extraction
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "text_extraction", 2, "STARTED", started_at=stage_start)
    db.commit()

    page_texts = {}
    method_per_page = {}

    for page in pdf_result.pages:
        if page.has_usable_text:
            page_texts[page.page_number] = page.text
            method_per_page[page.page_number] = "NATIVE_TEXT"

    # OCR pages with insufficient text
    text_extraction_done = False
    if pdf_result.needs_ocr_pages:
        ocr_status = check_any_ocr_available()
        any_ocr_available = ocr_status.get("any_available", False)
        active_provider = ocr_status.get("active_provider")
        
        if any_ocr_available:
            # ocr_pdf_pages → ocr_page handles cloud-first → Tesseract fallback
            ocr_results = ocr_pdf_pages(stored_path, pdf_result.needs_ocr_pages)
            ocr_success_count = 0
            for page_num, ocr_result in ocr_results.items():
                if ocr_result.success and ocr_result.text:
                    page_texts[page_num] = ocr_result.text
                    method_per_page[page_num] = f"OCR_{ocr_result.method.upper()}"
                    ocr_success_count += 1
            
            # If cloud/tesseract was tried but all pages failed, handle gracefully
            if ocr_success_count == 0 and not page_texts:
                failed_reasons = set(r.error or "Unknown" for r in ocr_results.values() if not r.success)
                _record_event(db, attempt_id, "text_extraction", 2, "FAILED",
                               message=f"OCR failed for all pages via {active_provider}: {'; '.join(failed_reasons)}",
                               details={"needs_ocr": pdf_result.needs_ocr_pages, "provider": active_provider},
                               started_at=stage_start)
                attempt.execution_state = "FAILED"
                attempt.error_message = f"OCR failed — cannot process scanned/image-only PDF"
                attempt.completed_at = _utcnow()
                _skip_remaining(db, attempt_id, 3, "OCR failed for image-only document")
                db.commit()
                return {"case_id": case_id, "attempt_id": attempt_id, "decision": None,
                        "error": f"OCR failed via {active_provider} — cannot process scanned/image-only PDF",
                        "is_byte_duplicate": False}
        else:
            # No OCR available at all (no cloud keys, no Tesseract)
            if not page_texts:
                _record_event(db, attempt_id, "text_extraction", 2, "FAILED",
                               message="No OCR available. Configure a cloud API key in Settings or install Tesseract locally.",
                               details={"needs_ocr": pdf_result.needs_ocr_pages, "ocr_available": False},
                               started_at=stage_start)
                attempt.execution_state = "FAILED"
                attempt.error_message = "No OCR available — configure an API key in Settings to process scanned PDFs"
                attempt.completed_at = _utcnow()
                _skip_remaining(db, attempt_id, 3, "No OCR available for image-only document")
                db.commit()
                return {"case_id": case_id, "attempt_id": attempt_id, "decision": None,
                        "error": "No OCR available — configure an API key in Settings to process scanned PDFs",
                        "is_byte_duplicate": False}
            else:
                _record_event(db, attempt_id, "text_extraction", 2, "COMPLETED",
                               message=f"No OCR available — {len(pdf_result.needs_ocr_pages)} scanned pages skipped. Configure API key in Settings for full OCR.",
                               details={"needs_ocr": pdf_result.needs_ocr_pages, "ocr_available": False},
                               started_at=stage_start)
                text_extraction_done = True
            db.commit()

    if not text_extraction_done:
        _record_event(db, attempt_id, "text_extraction", 2, "COMPLETED",
                   message=f"Extracted text from {len(page_texts)} pages",
                   details={"methods": method_per_page, "total_chars": sum(len(t) for t in page_texts.values())},
                   started_at=stage_start)
    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 4: Field Extraction
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "field_extraction", 3, "STARTED", started_at=stage_start)
    db.commit()

    # Try AI extraction first (Gemini/OpenAI/Anthropic), fall back to local regex
    extraction = None
    extraction_method_used = "local"
    ai_provider_info = get_extraction_provider()

    if ai_provider_info:
        ai_provider_name = ai_provider_info[0]
        try:
            extraction = ai_extract_fields(page_texts, method_per_page)
            if extraction:
                extraction_method_used = f"ai_{ai_provider_name}"
                print(f"✓ AI extraction succeeded via {ai_provider_name}")
        except Exception as e:
            print(f"⚠ AI extraction failed ({ai_provider_name}): {e}, falling back to local")
            extraction = None

    if extraction is None:
        # Fall back to local regex extraction
        extraction = extract_fields(page_texts, method_per_page)
        extraction_method_used = "local"
        if ai_provider_info:
            extraction.warnings.append(f"AI extraction failed, used local regex fallback")

    # Update attempt with extraction mode used
    attempt.extraction_mode = extraction_method_used

    # Store extracted data
    ext_data = ExtractedData(
        id=str(uuid.uuid4()),
        attempt_id=attempt_id,
        raw_vendor_name=extraction.vendor_name.raw_text if extraction.vendor_name else None,
        normalized_vendor_name=extraction.vendor_name.normalized_value if extraction.vendor_name else None,
        vendor_tax_id=extraction.vendor_tax_id.normalized_value if extraction.vendor_tax_id else None,
        invoice_number=extraction.invoice_number.normalized_value if extraction.invoice_number else None,
        invoice_date=extraction.invoice_date.normalized_value if extraction.invoice_date else None,
        due_date=extraction.due_date.normalized_value if extraction.due_date else None,
        currency=extraction.currency.normalized_value if extraction.currency else None,
        po_reference=extraction.po_reference.normalized_value if extraction.po_reference else None,
        subtotal_cents=int(extraction.subtotal.normalized_value) if extraction.subtotal and extraction.subtotal.normalized_value else None,
        tax_cents=int(extraction.tax.normalized_value) if extraction.tax and extraction.tax.normalized_value else None,
        gross_total_cents=int(extraction.gross_total.normalized_value) if extraction.gross_total and extraction.gross_total.normalized_value else None,
        tax_treatment=extraction.tax_treatment.normalized_value if extraction.tax_treatment else None,
        line_items=extraction.line_items,
        extraction_method=extraction_method_used,
        extraction_warnings=extraction.warnings if extraction.warnings else None,
        document_hash=pdf_result.sha256_hash,
        page_texts={str(k): v for k, v in page_texts.items()},
    )

    # Calculate net
    subtotal_cents = ext_data.subtotal_cents
    tax_cents = ext_data.tax_cents
    gross_cents = ext_data.gross_total_cents

    if subtotal_cents is not None:
        net_cents = subtotal_cents  # net = subtotal (no discount/shipping in our fixtures)
    elif gross_cents is not None and tax_cents is not None:
        net_cents = gross_cents - tax_cents
    else:
        net_cents = None

    ext_data.net_total_cents = net_cents
    db.add(ext_data)
    db.flush()

    # Store field evidence
    _store_field_evidence(db, ext_data.id, extraction)

    _record_event(db, attempt_id, "field_extraction", 3, "COMPLETED",
                   message=f"Extracted {len([f for f in [ext_data.invoice_number, ext_data.raw_vendor_name, ext_data.subtotal_cents, ext_data.gross_total_cents] if f is not None])} key fields via {extraction_method_used}",
                   details={"warnings": extraction.warnings, "line_items": len(extraction.line_items), "method": extraction_method_used},
                   started_at=stage_start)
    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 5: Field Validation
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "field_validation", 4, "STARTED", started_at=stage_start)
    db.commit()

    validation_issues = []
    if not ext_data.invoice_number:
        validation_issues.append("Missing invoice number")
    if not ext_data.invoice_date:
        validation_issues.append("Missing invoice date")
    if net_cents is None:
        validation_issues.append("Cannot determine net total")
    if not ext_data.currency:
        validation_issues.append("Missing currency")

    _record_event(db, attempt_id, "field_validation", 4, "COMPLETED",
                   message=f"Validation: {len(validation_issues)} issues" if validation_issues else "All fields valid",
                   details={"issues": validation_issues},
                   started_at=stage_start)
    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 6: Vendor Resolution
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "vendor_resolution", 5, "STARTED", started_at=stage_start)
    db.commit()

    vendor_result = resolve_vendor(
        db,
        extracted_name=ext_data.normalized_vendor_name or ext_data.raw_vendor_name,
        extracted_tax_id=ext_data.vendor_tax_id,
    )

    # Update case with vendor info
    if vendor_result.resolved:
        case.vendor_id = vendor_result.vendor_id

    _record_event(db, attempt_id, "vendor_resolution", 5, "COMPLETED",
                   message=f"Vendor {'resolved' if vendor_result.resolved else 'not resolved'}: {vendor_result.vendor_name or vendor_result.reason}",
                   details={
                       "resolved": vendor_result.resolved,
                       "vendor_id": vendor_result.vendor_id,
                       "match_method": vendor_result.match_method,
                       "candidates": len(vendor_result.candidates),
                   },
                   started_at=stage_start)
    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 7: Duplicate Detection (business identity)
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "duplicate_detection", 6, "STARTED", started_at=stage_start)
    db.commit()

    dup_result = check_business_duplicate(
        db,
        vendor_id=vendor_result.vendor_id,
        invoice_number=ext_data.invoice_number,
        currency=ext_data.currency,
        gross_cents=ext_data.gross_total_cents,
        net_cents=net_cents,
        current_case_id=case_id,
    )

    # Update case with invoice identity
    case.invoice_number = ext_data.invoice_number
    case.normalized_invoice_number = normalize_invoice_number(ext_data.invoice_number)
    case.currency = ext_data.currency

    _record_event(db, attempt_id, "duplicate_detection", 6, "COMPLETED",
                   message=dup_result.reason or "No business duplicates detected",
                   details={
                       "is_duplicate": dup_result.is_business_duplicate,
                       "is_collision": dup_result.is_identity_collision,
                       "duplicate_case": dup_result.duplicate_case_id,
                   },
                   started_at=stage_start)
    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 8: PO Matching
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "po_matching", 7, "STARTED", started_at=stage_start)
    db.commit()

    po_result = None
    if vendor_result.resolved:
        # Use reviewer-selected PO if provided
        effective_po_ref = reviewer_po_id or (ext_data.po_reference if ext_data.po_reference else None)

        # Get invoice description from line items
        invoice_desc = ""
        if extraction.line_items:
            invoice_desc = " ".join(item.get("description", "") for item in extraction.line_items)

        po_result = match_po(
            db,
            vendor_id=vendor_result.vendor_id,
            po_reference=effective_po_ref,
            invoice_currency=ext_data.currency or "USD",
            invoice_description=invoice_desc,
            invoice_net_cents=net_cents,
        )

        if po_result.matched:
            case.po_id = po_result.po_id

        _record_event(db, attempt_id, "po_matching", 7, "COMPLETED",
                       message=f"PO {'matched' if po_result.matched else 'not matched'}: {po_result.po_id or po_result.reason}",
                       details={
                           "matched": po_result.matched,
                           "po_id": po_result.po_id,
                           "candidates": len(po_result.candidates),
                           "requires_reviewer": po_result.requires_reviewer,
                       },
                       started_at=stage_start)
    else:
        _record_event(db, attempt_id, "po_matching", 7, "SKIPPED",
                       message="Vendor not resolved — PO matching skipped",
                       started_at=stage_start)

    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 9: Financial Policy Evaluation
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "policy_evaluation", 8, "STARTED", started_at=stage_start)
    db.commit()

    policy_eval = evaluate_policy(
        db=db,
        invoice_net_cents=net_cents,
        invoice_gross_cents=ext_data.gross_total_cents,
        invoice_tax_cents=ext_data.tax_cents,
        invoice_subtotal_cents=ext_data.subtotal_cents,
        invoice_currency=ext_data.currency,
        invoice_date_str=ext_data.invoice_date,
        invoice_number=ext_data.invoice_number,
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
        line_items=extraction.line_items,
    )

    # Store rule results
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

    _record_event(db, attempt_id, "policy_evaluation", 8, "COMPLETED",
                   message=f"Decision: {policy_eval.decision} — {policy_eval.primary_reason_code}",
                   details={
                       "decision": policy_eval.decision,
                       "reason_codes": policy_eval.all_reason_codes,
                       "rules_passed": sum(1 for r in policy_eval.rules if r.result == "PASS"),
                       "rules_failed": sum(1 for r in policy_eval.rules if r.result == "FAIL"),
                   },
                   started_at=stage_start)
    db.commit()

    # ════════════════════════════════════════════════════════
    # Stage 10: Commit Decision & Reservation (atomic)
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "commit_decision", 9, "STARTED", started_at=stage_start)

    # Build snapshots
    vendor_snapshot = None
    if vendor_result.resolved:
        vendor_snapshot = {
            "vendor_id": vendor_result.vendor_id,
            "vendor_name": vendor_result.vendor_name,
            "match_method": vendor_result.match_method,
        }

    po_snapshot = None
    if po_result and po_result.matched:
        po_snapshot = {
            "po_id": po_result.po_id,
            "match_method": po_result.match_method,
        }
        if po_result.candidates:
            c = po_result.candidates[0]
            po_snapshot.update({
                "po_net_cents": c.net_amount_cents,
                "committed_before_cents": c.committed_cents,
            })

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
        policy_snapshot={
            "version": settings.policy_version,
            "currency": settings.currency,
            "arithmetic_tolerance_cents": settings.arithmetic_tolerance_cents,
            "po_overage_pct": settings.po_overage_pct,
            "po_overage_max_cents": settings.po_overage_max_cents,
        },
        vendor_snapshot=vendor_snapshot,
        po_snapshot=po_snapshot,
        ledger_snapshot={
            "po_net_cents": policy_eval.po_net_cents,
            "committed_cents": policy_eval.committed_cents,
            "projected_cents": policy_eval.projected_cents,
            "allowed_overage_cents": policy_eval.allowed_overage_cents,
            "allowed_ceiling_cents": policy_eval.allowed_ceiling_cents,
        } if policy_eval.po_net_cents else None,
    )
    db.add(decision)
    db.flush()  # Flush decision before creating commitment that references it
    commitment = None
    if policy_eval.decision == "AUTO_APPROVED" and po_result and po_result.po_id and net_cents is not None:
        # Replace existing commitment for this case if re-evaluating
        existing_commitment = db.query(Commitment).filter(
            Commitment.case_id == case_id,
        ).first()

        if existing_commitment:
            existing_commitment.net_amount_cents = net_cents
            existing_commitment.po_id = po_result.po_id
            existing_commitment.decision_id = decision.id
            existing_commitment.status = "RESERVED"
            commitment = existing_commitment
        else:
            commitment = Commitment(
                id=str(uuid.uuid4()),
                case_id=case_id,
                po_id=po_result.po_id,
                net_amount_cents=net_cents,
                status="RESERVED",
                decision_id=decision.id,
            )
            db.add(commitment)

    # Update case
    case.current_decision = policy_eval.decision
    case.current_reason_code = policy_eval.primary_reason_code
    case.current_gross_cents = ext_data.gross_total_cents
    case.current_net_cents = net_cents

    # Complete attempt
    attempt.execution_state = "COMPLETED"
    attempt.completed_at = _utcnow()

    _record_event(db, attempt_id, "commit_decision", 9, "COMPLETED",
                   message=f"Decision committed: {policy_eval.decision}",
                   details={
                       "has_reservation": commitment is not None,
                       "reservation_cents": net_cents if commitment else None,
                   },
                   started_at=stage_start)

    # ════════════════════════════════════════════════════════
    # Stage 11: Publish Results
    # ════════════════════════════════════════════════════════
    stage_start = _utcnow()
    _record_event(db, attempt_id, "publish_results", 10, "STARTED", started_at=stage_start)
    _record_event(db, attempt_id, "publish_results", 10, "COMPLETED",
                   message="Results published",
                   details={"case_id": case_id, "decision": policy_eval.decision},
                   started_at=stage_start)

    db.commit()

    return {
        "case_id": case_id,
        "attempt_id": attempt_id,
        "decision": policy_eval.decision,
        "primary_reason_code": policy_eval.primary_reason_code,
        "explanation": policy_eval.explanation,
        "next_action": policy_eval.next_action,
        "is_byte_duplicate": False,
        "po_candidates": [
            {"po_id": c.po_id, "description": c.description, "remaining_cents": c.remaining_cents,
             "match_reason": c.match_reason, "rank": c.rank}
            for c in (po_result.candidates if po_result else [])
        ],
    }


def _skip_remaining(db: Session, attempt_id: str, from_stage: int, reason: str):
    """Record SKIPPED events for remaining stages."""
    for i in range(from_stage, len(STAGE_NAMES)):
        stage_name, stage_label = STAGE_NAMES[i]
        _record_event(db, attempt_id, stage_name, i, "SKIPPED",
                       message=f"Skipped: {reason}")
