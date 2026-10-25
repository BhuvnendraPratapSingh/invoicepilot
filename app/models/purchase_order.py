"""Purchase Order model."""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(String, primary_key=True)  # e.g. "PO-1001"
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False)
    description = Column(Text, nullable=True)
    service_scope = Column(Text, nullable=True)
    net_amount_cents = Column(Integer, nullable=False)  # in cents for precision
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(String, default="OPEN", nullable=False)  # OPEN, CLOSED, CANCELLED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vendor = relationship("Vendor", back_populates="purchase_orders")
    commitments = relationship("Commitment", back_populates="purchase_order")

    @property
    def net_amount_dollars(self):
        from decimal import Decimal
        return Decimal(self.net_amount_cents) / Decimal(100)
