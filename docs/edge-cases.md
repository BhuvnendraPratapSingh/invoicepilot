# InvoicePilot — Edge Cases

## Seed Data

| ID | Description | Relevant PO | Seed Commitment |
|---|---|---|---|
| SEED-CMT-001 | Prior partial invoice against PO-1002 | PO-1002 ($10,000 net) | $6,000 |
| SEED-CMT-002 | Initial cloud assessment | PO-1003 ($5,000 net) | $2,000 |

## Happy Path

**Fixture**: `happy_path_apex_invoice.pdf`
**Vendor**: Apex Digital Solutions (V-001) — Tax ID 84-2917365
**PO**: PO-1001 ($2,500 net, Website Redesign)
**Invoice**: INV-2026-0451, March 10, 2026
**Amounts**: Subtotal $2,500.00, Tax $200.00, Gross $2,700.00
**Expected**: AUTO_APPROVED, $2,500.00 net reservation on PO-1001

## Edge Family 1: Duplicates

### 1a. Identical Bytes
Upload `duplicate_original_meridian.pdf` twice.
**Expected**: Second upload returns byte-duplicate link. No new case or reservation.

### 1b. Reissued Duplicate
After original (MCG-2026-0088) is approved, upload `duplicate_reissued_meridian.pdf`.
Same vendor (V-002), same invoice number (MCG-2026-0088), same amounts ($3,500 net).
Different PDF layout/bytes.
**Expected**: BLOCKED / DUPLICATE_INVOICE. Links to original. No new reservation.

### 1c. Identity Collision
Upload `duplicate_collision_meridian.pdf`.
Same vendor (V-002), same invoice number (MCG-2026-0088), **different amount** ($3,800 net vs $3,500).
**Expected**: NEEDS_REVIEW / INVOICE_IDENTITY_COLLISION. May be correction or attempted duplicate.

## Edge Family 2: Cumulative Budget Tolerance

PO-1002: $10,000.00 net, $6,000.00 seed committed.
Overage: min($10,000 × 1%, $50) = **$50.00**. Ceiling: **$10,050.00**.

### 2a. Within Tolerance
**Fixture**: `cumulative_a_meridian.pdf` (MCG-2026-0201)
Net $4,040.00. Projected: $6,000 + $4,040 = $10,040.00 ≤ $10,050.00
**Expected**: AUTO_APPROVED with tolerance warning ($40 over PO net).

### 2b. Exceeds Tolerance (isolated)
**Fixture**: `cumulative_b_meridian.pdf` (MCG-2026-0202), fresh reset.
Net $4,060.00. Projected: $6,000 + $4,060 = $10,060.00 > $10,050.00
**Expected**: NEEDS_REVIEW / PO_CUMULATIVE_LIMIT_EXCEEDED. Exceeds by $10.00.

### 2c. Sequential A then C
Approve A first (committed: $6,000 + $4,040 = $10,040).
Then upload `cumulative_c_meridian.pdf` (MCG-2026-0203), net $20.00.
Projected: $10,040 + $20 = $10,060 > $10,050.
**Expected**: NEEDS_REVIEW. Small follow-up does NOT get a fresh tolerance.

## Edge Family 3: Ambiguous PO

**Fixture**: `ambiguous_po_brightwave.pdf` (BW-INV-2026-055)
**Vendor**: Brightwave Analytics (V-005) — two open POs:
- PO-1005: Data Pipeline Development ($3,000 net)
- PO-1006: BI Dashboards ($2,800 net)

Invoice: No PO reference, bundled "data analytics and reporting" description, net $1,500.
**Expected**: NEEDS_REVIEW / PO_AMBIGUOUS. Both candidates displayed.

**Reviewer Action**: Select PO-1005 with reason. System re-evaluates all rules.
**Expected after review**: AUTO_APPROVED (if PO has capacity).

## Edge Family 4: Scanned / Missing Invoice Number

**Fixture**: `scanned_missing_number_pinnacle.pdf`
Image-only PDF (no text layer). Vendor: Pinnacle Cloud Services (V-003).
Invoice number genuinely absent from document.
Net $800.00, Tax $64.00, Gross $864.00.
**Expected**: OCR runs (if Tesseract available). NEEDS_INFORMATION / MISSING_INVOICE_NUMBER.
No reservation. Information request preview shown.

**Correction**: Upload `scanned_corrected_pinnacle.pdf` as revision.
Contains invoice number PCS-2026-0312.
**Expected**: Re-evaluates. AUTO_APPROVED with original evidence preserved.
