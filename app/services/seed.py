"""Seed data loading from CSV files into the database."""

import csv
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.vendor import Vendor, VendorAlias
from app.models.purchase_order import PurchaseOrder
from app.models.invoice import Commitment, InvoiceCase

SEED_DIR = Path("data/seed")


def normalize_name(name: str) -> str:
    """Normalize vendor name: lowercase, strip whitespace, collapse spaces."""
    return " ".join(name.lower().strip().split())


def load_vendors(db: Session):
    """Load vendors and aliases from CSV."""
    path = SEED_DIR / "vendors.csv"
    if not path.exists():
        return

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor = Vendor(
                id=row["id"].strip(),
                name=row["name"].strip(),
                normalized_name=normalize_name(row["name"]),
                tax_id=row.get("tax_id", "").strip() or None,
                address=row.get("address", "").strip() or None,
                is_active=row.get("is_active", "true").strip().lower() == "true",
            )
            db.add(vendor)

            # Load aliases
            aliases_str = row.get("aliases", "").strip()
            if aliases_str:
                for i, alias in enumerate(aliases_str.split(";")):
                    alias = alias.strip()
                    if alias:
                        va = VendorAlias(
                            id=f"{row['id']}-A{i+1:03d}",
                            vendor_id=row["id"].strip(),
                            alias_name=alias,
                            normalized_alias=normalize_name(alias),
                        )
                        db.add(va)

    db.commit()


def load_purchase_orders(db: Session):
    """Load purchase orders from CSV."""
    path = SEED_DIR / "purchase_orders.csv"
    if not path.exists():
        return

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            po = PurchaseOrder(
                id=row["id"].strip(),
                vendor_id=row["vendor_id"].strip(),
                description=row.get("description", "").strip() or None,
                service_scope=row.get("service_scope", "").strip() or None,
                net_amount_cents=int(row["net_amount_cents"]),
                currency=row.get("currency", "USD").strip(),
                status=row.get("status", "OPEN").strip(),
            )
            db.add(po)

    db.commit()


def load_seed_commitments(db: Session):
    """Load historical commitments that represent prior invoicing against POs."""
    path = SEED_DIR / "commitments.csv"
    if not path.exists():
        return

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Create placeholder case for seeded commitments
            case_id = row["case_id"].strip()
            existing = db.query(InvoiceCase).filter_by(id=case_id).first()
            if not existing:
                case = InvoiceCase(
                    id=case_id,
                    vendor_id=None,
                    current_decision="AUTO_APPROVED",
                    current_reason_code="HISTORICAL_SEED",
                )
                db.add(case)

            commitment = Commitment(
                id=row["id"].strip(),
                case_id=case_id,
                po_id=row["po_id"].strip(),
                net_amount_cents=int(row["net_amount_cents"]),
                status=row.get("status", "RESERVED").strip(),
            )
            db.add(commitment)

    db.commit()


def seed_all(db: Session):
    """Load all seed data in order."""
    load_vendors(db)
    load_purchase_orders(db)
    load_seed_commitments(db)
