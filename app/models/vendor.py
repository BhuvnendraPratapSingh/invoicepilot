"""Vendor and VendorAlias models."""

from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String, primary_key=True)  # e.g. "V-001"
    name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=False, index=True)
    tax_id = Column(String, nullable=True, index=True)
    address = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    aliases = relationship("VendorAlias", back_populates="vendor", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")


class VendorAlias(Base):
    __tablename__ = "vendor_aliases"

    id = Column(String, primary_key=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False)
    alias_name = Column(String, nullable=False)
    normalized_alias = Column(String, nullable=False, index=True)

    vendor = relationship("Vendor", back_populates="aliases")
