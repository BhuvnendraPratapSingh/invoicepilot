"""Vendor resolution against approved vendor master.

Rules:
- Prefer unique trusted tax/vendor ID exact match
- Otherwise exact normalized name or alias match
- Fuzzy name similarity suggests candidates but cannot approve
- Conflicting/unknown/inactive vendors cannot auto-approve
"""

from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session
from app.models.vendor import Vendor, VendorAlias
from app.services.seed import normalize_name


@dataclass
class VendorCandidate:
    vendor_id: str
    vendor_name: str
    match_method: str  # TAX_ID, EXACT_NAME, ALIAS, FUZZY
    confidence: str  # HIGH, MEDIUM, LOW
    matched_value: str
    is_active: bool


@dataclass
class VendorResolutionResult:
    resolved: bool = False
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    match_method: Optional[str] = None
    candidates: list[VendorCandidate] = field(default_factory=list)
    reason: Optional[str] = None
    is_active: bool = True


def resolve_vendor(
    db: Session,
    extracted_name: Optional[str],
    extracted_tax_id: Optional[str],
) -> VendorResolutionResult:
    """Resolve vendor identity against the approved vendor master."""

    result = VendorResolutionResult()

    # 1. Try tax ID exact match (preferred)
    if extracted_tax_id:
        clean_tax_id = extracted_tax_id.strip().replace(' ', '')
        vendor = db.query(Vendor).filter(Vendor.tax_id == clean_tax_id).first()
        if vendor:
            result.candidates.append(VendorCandidate(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                match_method="TAX_ID",
                confidence="HIGH",
                matched_value=clean_tax_id,
                is_active=vendor.is_active,
            ))
            if vendor.is_active:
                result.resolved = True
                result.vendor_id = vendor.id
                result.vendor_name = vendor.name
                result.match_method = "TAX_ID"
                result.is_active = True
                return result
            else:
                result.reason = f"Vendor '{vendor.name}' matched by Tax ID but is INACTIVE"
                result.is_active = False
                return result

    # 2. Try exact normalized name match
    if extracted_name:
        norm_name = normalize_name(extracted_name)

        # Direct name match
        vendor = db.query(Vendor).filter(Vendor.normalized_name == norm_name).first()
        if vendor:
            result.candidates.append(VendorCandidate(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                match_method="EXACT_NAME",
                confidence="HIGH",
                matched_value=norm_name,
                is_active=vendor.is_active,
            ))
            if vendor.is_active:
                result.resolved = True
                result.vendor_id = vendor.id
                result.vendor_name = vendor.name
                result.match_method = "EXACT_NAME"
                result.is_active = True
                return result
            else:
                result.reason = f"Vendor '{vendor.name}' matched by name but is INACTIVE"
                result.is_active = False
                return result

        # 3. Try alias match
        alias = db.query(VendorAlias).filter(VendorAlias.normalized_alias == norm_name).first()
        if alias:
            vendor = db.query(Vendor).filter(Vendor.id == alias.vendor_id).first()
            if vendor:
                result.candidates.append(VendorCandidate(
                    vendor_id=vendor.id,
                    vendor_name=vendor.name,
                    match_method="ALIAS",
                    confidence="HIGH",
                    matched_value=alias.alias_name,
                    is_active=vendor.is_active,
                ))
                if vendor.is_active:
                    result.resolved = True
                    result.vendor_id = vendor.id
                    result.vendor_name = vendor.name
                    result.match_method = "ALIAS"
                    result.is_active = True
                    return result
                else:
                    result.reason = f"Vendor '{vendor.name}' matched by alias but is INACTIVE"
                    result.is_active = False
                    return result

        # 4. Fuzzy suggestions (never auto-approve)
        all_vendors = db.query(Vendor).filter(Vendor.is_active == True).all()
        for v in all_vendors:
            # Simple substring/overlap check
            if _name_overlap(norm_name, v.normalized_name) > 0.5:
                result.candidates.append(VendorCandidate(
                    vendor_id=v.id,
                    vendor_name=v.name,
                    match_method="FUZZY",
                    confidence="LOW",
                    matched_value=v.name,
                    is_active=v.is_active,
                ))

            # Check aliases too
            for alias in v.aliases:
                if _name_overlap(norm_name, alias.normalized_alias) > 0.5:
                    if not any(c.vendor_id == v.id for c in result.candidates):
                        result.candidates.append(VendorCandidate(
                            vendor_id=v.id,
                            vendor_name=v.name,
                            match_method="FUZZY",
                            confidence="LOW",
                            matched_value=alias.alias_name,
                            is_active=v.is_active,
                        ))

    if not result.candidates:
        result.reason = f"No matching vendor found for: {extracted_name or '(unknown)'}"
    elif not result.resolved:
        result.reason = f"Vendor candidates found but no confirmed match (fuzzy only)"

    return result


def _name_overlap(a: str, b: str) -> float:
    """Simple word-overlap similarity between two normalized names."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))
