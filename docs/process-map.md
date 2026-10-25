# InvoicePilot — Process Map

## Overview

InvoicePilot processes vendor PDF invoices through a deterministic pipeline:
PDF → Extract → Validate → Match → Decide → Reserve/Review.

AI helps interpret documents. Explicit financial controls decide what proceeds.
Every decision points to evidence. Unresolved uncertainty has an actionable next step.

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INVOICE PROCESSING PIPELINE                       │
├──────────┬──────────────────────────────────────────────────────────────┤
│ Stage 1  │ RECEIVE & VALIDATE PDF                                       │
│          │ • Assign opaque run ID                                        │
│          │ • Calculate SHA-256 hash                                      │
│          │ • Check size (≤10MB), pages (≤20), validity                   │
│          │ • Store original file with generated safe name                │
│          │ → FAIL: corrupt/encrypted/oversized → FAILED + clear error    │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 2  │ DUPLICATE BYTE CHECK                                         │
│          │ • Match SHA-256 against all stored documents                  │
│          │ • Same bytes → link to existing case, record repeat event     │
│          │ • No new processing case created                              │
│          │ → DUPLICATE BYTES: return link to original case               │
│          │ → NEW: continue to Stage 3                                    │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 3  │ TEXT EXTRACTION (page by page)                                │
│          │ • Native text via PyMuPDF per page                            │
│          │ • If page text < threshold → OCR via Tesseract                │
│          │ • Record method per page (NATIVE_TEXT / OCR)                  │
│          │ → FAIL: no usable text on any page → NEEDS_INFORMATION        │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 4  │ FIELD EXTRACTION                                             │
│          │ • Local mode: regex/pattern extraction from text              │
│          │ • AI mode (optional): Anthropic structured extraction         │
│          │ • Schema: vendor, invoice#, date, PO ref, lines, totals      │
│          │ • Provenance per field: raw text, page, method, status        │
│          │ → Missing required fields → noted, continue to collect all    │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 5  │ VALIDATION                                                    │
│          │ • Required field completeness                                 │
│          │ • Date validity (not future)                                  │
│          │ • Currency = USD                                              │
│          │ • Arithmetic: line sums, subtotal, net, tax, gross            │
│          │ • Tolerance: $0.01                                            │
│          │ → Failures recorded but pipeline continues for full picture   │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 6  │ VENDOR RESOLUTION                                            │
│          │ • Tax/vendor ID exact match (preferred)                       │
│          │ • Exact normalized name or alias match                        │
│          │ • Fuzzy suggestions for review (never auto-approve)           │
│          │ • Check vendor is active                                      │
│          │ → FAIL: unknown/inactive/ambiguous → NEEDS_REVIEW             │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 7  │ DUPLICATE DETECTION (business identity)                      │
│          │ • Vendor ID + normalized invoice number                       │
│          │ • Same identity + same amounts + active approval → BLOCKED    │
│          │ • Same identity + different amounts → IDENTITY_COLLISION      │
│          │ • Similar amount/date/vendor → suspected duplicate warning    │
│          │ → BLOCKED/NEEDS_REVIEW as appropriate                         │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 8  │ PO MATCHING                                                  │
│          │ • Explicit PO ref: validate exists, belongs to vendor, open   │
│          │ • No PO ref: search eligible POs, rank candidates             │
│          │ • Ambiguous/multiple candidates → NEEDS_REVIEW                │
│          │ • No eligible PO → NEEDS_REVIEW                               │
│          │ → Single unambiguous match → continue                         │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 9  │ FINANCIAL POLICY EVALUATION                                  │
│          │ • Compare invoice_net to PO remaining capacity                │
│          │ • Cumulative: committed + current ≤ PO_net + overage          │
│          │ • Overage = min(PO_net * 0.01, $50.00)                        │
│          │ • Net vs gross comparison (never compare gross to net PO)     │
│          │ → PASS/FAIL with full arithmetic evidence                     │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 10 │ DECISION & RESERVATION (atomic transaction)                  │
│          │ • Re-check duplicates and PO exposure in transaction          │
│          │ • AUTO_APPROVED → create reservation                          │
│          │ • NEEDS_REVIEW → no reservation                               │
│          │ • NEEDS_INFORMATION → no reservation                          │
│          │ • BLOCKED → no reservation                                    │
│          │ → Commit decision + reservation + events atomically           │
├──────────┼──────────────────────────────────────────────────────────────┤
│ Stage 11 │ PUBLISH RESULTS                                              │
│          │ • Decision with evidence and explanation                      │
│          │ • Next action and responsible role                            │
│          │ • Audit bundle available for export                           │
│          │ • Page images rendered for evidence display                   │
└──────────┴──────────────────────────────────────────────────────────────┘
```

## Human Handoff Points

| Trigger | Actor | Action | System Response |
|---|---|---|---|
| NEEDS_REVIEW (ambiguous PO) | AP Reviewer | Select PO + reason | Re-evaluate all rules against current state |
| NEEDS_REVIEW (vendor unclear) | AP Reviewer | Confirm vendor + reason | Re-evaluate |
| NEEDS_REVIEW (tolerance exceeded) | PO Owner / AP | Amend PO or reject | Re-evaluate or close case |
| NEEDS_REVIEW (identity collision) | AP Reviewer | Link as correction or reject | Re-evaluate with new context |
| NEEDS_INFORMATION (missing field) | Vendor / AP | Attach corrected PDF | New revision, re-evaluate |
| BLOCKED (duplicate) | AP Reviewer | Acknowledge or dispute | Link to original for inspection |

## Key Invariants

1. No reservation without AUTO_APPROVED decision
2. No decision without completed extraction and evaluation
3. Failed stages block dependent stages but independent checks continue
4. History is append-only — corrections create new revisions
5. Cumulative PO exposure is always current at decision time (checked in transaction)
