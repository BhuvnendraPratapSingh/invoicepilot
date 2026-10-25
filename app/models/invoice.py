"""Invoice processing models — cases, documents, attempts, events, decisions."""

from sqlalchemy import (
    Column, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db import Base
import uuid


def _new_id():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


class InvoiceCase(Base):
    """Top-level entity: one invoice case per unique business invoice."""
    __tablename__ = "invoice_cases"

    id = Column(String, primary_key=True, default=_new_id)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=True)
    invoice_number = Column(String, nullable=True)
    normalized_invoice_number = Column(String, nullable=True, index=True)
    currency = Column(String(3), nullable=True)
    current_decision = Column(String, nullable=True)  # AUTO_APPROVED, NEEDS_REVIEW, NEEDS_INFORMATION, BLOCKED
    current_reason_code = Column(String, nullable=True)
    current_gross_cents = Column(Integer, nullable=True)
    current_net_cents = Column(Integer, nullable=True)
    po_id = Column(String, ForeignKey("purchase_orders.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    source_documents = relationship("SourceDocument", back_populates="case", cascade="all, delete-orphan")
    processing_attempts = relationship("ProcessingAttempt", back_populates="case", cascade="all, delete-orphan",
                                       order_by="ProcessingAttempt.created_at")
    decisions = relationship("Decision", back_populates="case", cascade="all, delete-orphan")
    commitments = relationship("Commitment", back_populates="case", cascade="all, delete-orphan")
    review_actions = relationship("ReviewAction", back_populates="case", cascade="all, delete-orphan")


class SourceDocument(Base):
    """A PDF file attached to a case (original or corrected revision)."""
    __tablename__ = "source_documents"

    id = Column(String, primary_key=True, default=_new_id)
    case_id = Column(String, ForeignKey("invoice_cases.id"), nullable=False)
    revision_number = Column(Integer, default=1, nullable=False)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)  # safe generated name
    sha256_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=True)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("InvoiceCase", back_populates="source_documents")


class ProcessingAttempt(Base):
    """One processing run through the pipeline."""
    __tablename__ = "processing_attempts"

    id = Column(String, primary_key=True, default=_new_id)
    case_id = Column(String, ForeignKey("invoice_cases.id"), nullable=False)
    source_document_id = Column(String, nullable=True)  # Set after document stored
    attempt_number = Column(Integer, default=1, nullable=False)
    execution_state = Column(String, default="QUEUED", nullable=False)  # QUEUED, RUNNING, COMPLETED, FAILED, INTERRUPTED
    trigger = Column(String, default="upload", nullable=False)  # upload, retry, review, revision
    extraction_mode = Column(String, default="local", nullable=False)  # local, ai_assisted
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("InvoiceCase", back_populates="processing_attempts")
    stage_events = relationship("StageEvent", back_populates="attempt", cascade="all, delete-orphan",
                                order_by="StageEvent.stage_order")
    extracted_data = relationship("ExtractedData", back_populates="attempt", cascade="all, delete-orphan")
    rule_results = relationship("RuleResult", back_populates="attempt", cascade="all, delete-orphan")


class StageEvent(Base):
    """Individual stage start/complete/fail events within a processing attempt."""
    __tablename__ = "stage_events"

    id = Column(String, primary_key=True, default=_new_id)
    attempt_id = Column(String, ForeignKey("processing_attempts.id"), nullable=False)
    stage_name = Column(String, nullable=False)
    stage_order = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # STARTED, COMPLETED, FAILED, SKIPPED
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    attempt = relationship("ProcessingAttempt", back_populates="stage_events")


class ExtractedData(Base):
    """Structured extracted invoice data for one attempt."""
    __tablename__ = "extracted_data"

    id = Column(String, primary_key=True, default=_new_id)
    attempt_id = Column(String, ForeignKey("processing_attempts.id"), nullable=False)
    raw_vendor_name = Column(String, nullable=True)
    normalized_vendor_name = Column(String, nullable=True)
    vendor_tax_id = Column(String, nullable=True)
    vendor_address = Column(Text, nullable=True)
    invoice_number = Column(String, nullable=True)
    invoice_date = Column(String, nullable=True)
    due_date = Column(String, nullable=True)
    currency = Column(String(3), nullable=True)
    po_reference = Column(String, nullable=True)
    subtotal_cents = Column(Integer, nullable=True)
    discount_cents = Column(Integer, nullable=True)
    shipping_cents = Column(Integer, nullable=True)
    tax_cents = Column(Integer, nullable=True)
    gross_total_cents = Column(Integer, nullable=True)
    net_total_cents = Column(Integer, nullable=True)  # computed: subtotal - discount + shipping
    tax_treatment = Column(String, nullable=True)  # EXCLUSIVE, INCLUSIVE, UNKNOWN
    line_items = Column(JSON, nullable=True)  # list of line item dicts
    extraction_method = Column(String, nullable=False)  # local, ai_assisted
    extraction_warnings = Column(JSON, nullable=True)
    document_hash = Column(String(64), nullable=True)
    page_texts = Column(JSON, nullable=True)  # {page_num: text} for evidence
    created_at = Column(DateTime, default=_utcnow)

    attempt = relationship("ProcessingAttempt", back_populates="extracted_data")
    field_evidences = relationship("FieldEvidence", back_populates="extracted_data", cascade="all, delete-orphan")


class FieldEvidence(Base):
    """Per-field provenance and evidence."""
    __tablename__ = "field_evidences"

    id = Column(String, primary_key=True, default=_new_id)
    extracted_data_id = Column(String, ForeignKey("extracted_data.id"), nullable=False)
    field_name = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    normalized_value = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    text_span = Column(String, nullable=True)  # surrounding context
    bbox = Column(JSON, nullable=True)  # [x0, y0, x1, y1] if available
    method = Column(String, nullable=False)  # NATIVE_TEXT, OCR, MODEL_INTERPRETATION, DERIVED_ARITHMETIC, HUMAN_CORRECTION
    verification_status = Column(String, default="UNCERTAIN")  # VERIFIED, UNCERTAIN, MISSING
    is_explicitly_present = Column(Boolean, default=True)  # vs computed/derived

    extracted_data = relationship("ExtractedData", back_populates="field_evidences")


class RuleResult(Base):
    """Individual rule evaluation result."""
    __tablename__ = "rule_results"

    id = Column(String, primary_key=True, default=_new_id)
    attempt_id = Column(String, ForeignKey("processing_attempts.id"), nullable=False)
    rule_id = Column(String, nullable=False)
    rule_name = Column(String, nullable=False)
    result = Column(String, nullable=False)  # PASS, FAIL, WARN, NOT_EVALUATED
    observed_value = Column(String, nullable=True)
    expected_value = Column(String, nullable=True)
    explanation = Column(Text, nullable=True)
    evidence_refs = Column(JSON, nullable=True)
    severity = Column(String, default="ERROR")  # ERROR, WARNING, INFO

    attempt = relationship("ProcessingAttempt", back_populates="rule_results")


class Decision(Base):
    """Business decision for a processing attempt."""
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=_new_id)
    case_id = Column(String, ForeignKey("invoice_cases.id"), nullable=False)
    attempt_id = Column(String, ForeignKey("processing_attempts.id"), nullable=False)
    decision = Column(String, nullable=False)  # AUTO_APPROVED, NEEDS_REVIEW, NEEDS_INFORMATION, BLOCKED
    primary_reason_code = Column(String, nullable=False)
    all_reason_codes = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=False)
    next_action = Column(Text, nullable=True)
    responsible_role = Column(String, nullable=True)
    policy_version = Column(String, nullable=False)
    policy_snapshot = Column(JSON, nullable=True)
    vendor_snapshot = Column(JSON, nullable=True)
    po_snapshot = Column(JSON, nullable=True)
    ledger_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("InvoiceCase", back_populates="decisions")


class Commitment(Base):
    """Budget reservation against a PO. One per approved invoice case."""
    __tablename__ = "commitments"

    id = Column(String, primary_key=True, default=_new_id)
    case_id = Column(String, ForeignKey("invoice_cases.id"), nullable=False)
    po_id = Column(String, ForeignKey("purchase_orders.id"), nullable=False)
    net_amount_cents = Column(Integer, nullable=False)
    status = Column(String, default="RESERVED", nullable=False)  # RESERVED, POSTED, PAID, CANCELLED
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Unique: one active commitment per case
    __table_args__ = (
        UniqueConstraint("case_id", "po_id", name="uq_commitment_case_po"),
    )

    case = relationship("InvoiceCase", back_populates="commitments")
    purchase_order = relationship("PurchaseOrder", back_populates="commitments")


class ReviewAction(Base):
    """Human review action on a case."""
    __tablename__ = "review_actions"

    id = Column(String, primary_key=True, default=_new_id)
    case_id = Column(String, ForeignKey("invoice_cases.id"), nullable=False)
    action_type = Column(String, nullable=False)  # SELECT_PO, CORRECT_FIELD, ATTACH_REVISION, ACKNOWLEDGE_DUPLICATE
    actor = Column(String, default="demo-reviewer", nullable=False)
    reason = Column(Text, nullable=True)
    before_value = Column(String, nullable=True)
    after_value = Column(String, nullable=True)
    field_name = Column(String, nullable=True)
    source_document_id = Column(String, ForeignKey("source_documents.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("InvoiceCase", back_populates="review_actions")
