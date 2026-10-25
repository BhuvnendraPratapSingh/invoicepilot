"""Database models — import all to register with SQLAlchemy."""

from app.models.vendor import Vendor, VendorAlias
from app.models.purchase_order import PurchaseOrder
from app.models.invoice import (
    InvoiceCase,
    SourceDocument,
    ProcessingAttempt,
    StageEvent,
    ExtractedData,
    FieldEvidence,
    RuleResult,
    Decision,
    Commitment,
    ReviewAction,
)
from app.models.settings import AppSetting

all_models = [
    Vendor, VendorAlias, PurchaseOrder,
    InvoiceCase, SourceDocument, ProcessingAttempt,
    StageEvent, ExtractedData, FieldEvidence,
    RuleResult, Decision, Commitment, ReviewAction,
    AppSetting,
]
