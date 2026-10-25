# Advanced Edge Cases — Demo Walkthrough

## Prerequisites
- Server running on port 8000 (or 8111 for QA)
- Reset baseline: `POST /api/demo/reset`
- Tesseract OCR installed for Scenario D

## Scenario A: Stale Review (PO balance changes during review)

**Shows**: The system re-evaluates against current state, not cached balances.

1. Reset baseline
2. Upload `adv_stale_review_a.pdf` — Meridian invoice, $4,000, no PO reference
3. Observe: NEEDS_REVIEW / PO_AMBIGUOUS (two candidate POs for Meridian)
4. **Do NOT resolve yet** — leave it in review
5. Upload `adv_stale_review_b.pdf` — Meridian invoice, $200, explicit PO-1002
6. Observe: AUTO_APPROVED, $200 committed against PO-1002
7. Return to Invoice A's case → Select PO-1002, enter reason, Re-evaluate
8. Observe: NEEDS_REVIEW / PO_CUMULATIVE_LIMIT_EXCEEDED
   - Committed: $6,200 (seed $6,000 + Invoice B $200)
   - Projected: $10,200 ($6,200 + $4,000)
   - Ceiling: $10,050
   - Excess: $150

**Key point**: The reviewer's PO selection resolved the ambiguity but revealed a budget problem that didn't exist when Invoice A was first submitted.

## Scenario B: Correction After Approval

**Shows**: A corrected invoice doesn't silently replace an approved liability.

1. Reset baseline
2. Upload `adv_correction_original.pdf` — Apex, ADV-CORR-1042, $2,000 net
3. Observe: AUTO_APPROVED, $2,000 committed on PO-1001
4. Upload `adv_correction_revised.pdf` — same invoice number, $2,300 net
5. Observe: NEEDS_REVIEW / INVOICE_IDENTITY_COLLISION
6. Original $2,000 commitment is unchanged
7. No new commitment created for the correction

**Key point**: Same invoice number + different amount = review, not automatic replacement.

## Scenario C: PO Belongs to Another Vendor

**Shows**: The system catches vendor/PO ownership conflicts.

1. Reset baseline
2. Upload `adv_wrong_vendor_po.pdf` — Apex vendor citing PO-1002 (Meridian's PO)
3. Observe: NEEDS_REVIEW — "PO 'PO-1002' belongs to vendor V-002, not V-001"
4. No commitment created despite PO having ample capacity

**Key point**: A valid PO with budget doesn't authorize payment to the wrong vendor.

## Scenario D: OCR with Distractor Identifiers

**Shows**: OCR correctly distinguishes invoice numbers from other identifiers.

1. Reset baseline
2. Upload `adv_ocr_distractors.pdf` — scanned image-only PDF
3. Contains: Account# ACCT-88421, Service Ref SVC-REF-2026-Q1, PO PO-1003 — but NO invoice number
4. Observe: NEEDS_INFORMATION / MISSING_INVOICE_NUMBER
5. PO reference correctly extracted as PO-1003
6. Invoice number stays null (not confused with account# or service ref)
7. Attach `adv_ocr_distractors_corrected.pdf` as revision
8. Observe: invoice number PCS-ADV-2026-0099 extracted, appropriate decision returned

**Key point**: The system doesn't fabricate an invoice number from nearby identifiers.

## Fixture Files
| Scenario | File | Description |
|---|---|---|
| A | `adv_stale_review_a.pdf` | Meridian, $4,000, no PO ref |
| A | `adv_stale_review_b.pdf` | Meridian, $200, explicit PO-1002 |
| B | `adv_correction_original.pdf` | Apex, ADV-CORR-1042, $2,000 |
| B | `adv_correction_revised.pdf` | Apex, ADV-CORR-1042, $2,300 (correction) |
| C | `adv_wrong_vendor_po.pdf` | Apex citing Meridian's PO-1002 |
| D | `adv_ocr_distractors.pdf` | Scanned, no invoice#, has distractors |
| D | `adv_ocr_distractors_corrected.pdf` | Corrected with invoice# added |
