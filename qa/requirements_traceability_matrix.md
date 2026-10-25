# Requirements Traceability Matrix — InvoicePilot

## Original Assignment Reference

**Source:** `asa-case-study-candidate (2) (1) (1) (1).pdf` — PS-1 Invoice Processing
**Status:** Original assignment accessible and reviewed

## Assignment Requirements (from Problem Statement)

### PS-1 Core Requirements

| ID | Clause | Required Behavior | Current Support | Gap |
|----|--------|-------------------|-----------------|-----|
| R-01 | "takes an invoice as input" | Accept PDF invoices | ✅ PDF upload works | None |
| R-02 | "produces a clear, reasoned decision as output" | Decision + explanation | ✅ AUTO_APPROVED/NEEDS_REVIEW/NEEDS_INFORMATION/BLOCKED with explanation | None |
| R-03 | "everything that happened in between visible" | Stage-by-stage visibility | ✅ StageEvent records, UI live view | None |
| R-04 | "Different vendors format them differently" | Handle varied layouts | ✅ Pattern-based extraction with fallbacks | Columnar PDFs need improvement |
| R-05 | "Some are clean PDFs with machine-readable text" | Native text extraction | ✅ PyMuPDF native extraction | None |
| R-06 | "Some are scanned images" | OCR support | ✅ Tesseract integration (graceful fallback when unavailable) | None |
| R-07 | "Line items might be itemised or bundled" | Both invoice types | ✅ Bundled supported, itemized partial | Line items extraction needs enhancement |
| R-08 | "Tax might be embedded or separated" | Tax handling | ⚠️ Partial — separated tax works, embedded tax derivation not implemented | Gap |
| R-09 | "PO references might be explicit or implied" | PO matching | ✅ Explicit works, ambiguous routes to review | Implied PO contextual matching not implemented |
| R-10 | "sometimes critical information is just missing" | Missing field handling | ✅ NEEDS_INFORMATION for missing invoice#/date/totals | None |
| R-11 | "approved vendors" | Vendor master lookup | ✅ Vendor resolution with tax ID/name matching | None |
| R-12 | "PO amounts, tolerance thresholds" | PO capacity with tolerance | ✅ min(1%, $50) cumulative tolerance | None |
| R-13 | "duplicate detection rules" | Duplicate handling | ✅ Byte-duplicate, business duplicate, identity collision | None |
| R-14 | "A vendor might split a single PO into multiple invoices" | Split invoices | ✅ Cumulative commitment tracking | None |
| R-15 | "Amounts might be close but not exact" | Arithmetic tolerance | ✅ $0.01 tolerance | None |
| R-16 | "You decide what to extract" | Field schema | ✅ Comprehensive schema (vendor, invoice, PO, amounts) | Order ID, shipping, discount fields not extracted |
| R-17 | "how to validate" | Validation rules | ✅ Policy engine with 10+ rules | None |
| R-18 | "Design and build 2–4 edge cases" | Edge case coverage | ✅ 4 families: Duplicates, Cumulative Budget, Ambiguous PO, Missing Info | None |

## Project Policy Choices (not assignment requirements)

| Policy | Current Value | Source |
|--------|---------------|--------|
| Arithmetic tolerance | $0.01 | config.py |
| Cumulative PO overage | min(1% of PO net, $50) | policy_engine.py |
| Currency support | USD only | Derived from fixtures |
| Service-only invoices | Yes | Implied by fixture design |

## Identified Gaps

### Gap 1: Order ID / Reference Extraction
**Assignment relevance:** R-16 "You decide what to extract" — Order ID is a common field
**Current state:** Not extracted
**Impact:** Low — not required for decision logic

### Gap 2: Discount and Shipping Extraction
**Assignment relevance:** R-16 — common invoice fields
**Current state:** Schema fields exist but not extracted
**Impact:** Medium — affects reconciliation accuracy

### Gap 3: Columnar PDF Layout
**Assignment relevance:** R-04 "Different vendors format them differently"
**Current state:** Partial support with fallback
**Impact:** Medium — SuperStore PDFs show amounts in wrong association

### Gap 4: Tax-Inclusive Derivation
**Assignment relevance:** R-08 "Tax might be embedded"
**Current state:** Not implemented
**Impact:** Medium — cannot derive net from tax-inclusive gross

### Gap 5: Line Items Full Extraction
**Assignment relevance:** R-07 "Line items might be itemised"
**Current state:** Partial — extracts some line items
**Impact:** Low-Medium — reconciliation less precise

## Test Coverage Matrix

| Requirement | Test Evidence | Test File |
|-------------|---------------|-----------|
| R-01 PDF upload | ✅ 28/28 edge cases pass | test_edge_cases.py |
| R-02 Decision output | ✅ Happy path AUTO_APPROVED | test_edge_cases.py |
| R-03 Stage visibility | ✅ UI live view verified | Manual + DEMO_READINESS.md |
| R-04 Varied layouts | ⚠️ 5 vendor fixtures | test_edge_cases.py |
| R-05 Native text | ✅ All happy path tests | test_edge_cases.py |
| R-06 OCR | ✅ Graceful fallback tested | Family 4: Scanned |
| R-10 Missing fields | ✅ NEEDS_INFORMATION | Family 4 |
| R-11 Vendor lookup | ✅ Resolution works | All tests |
| R-12 PO tolerance | ✅ Cumulative tests | Family 2 |
| R-13 Duplicates | ✅ 3 scenarios | Family 1 |
| R-14 Split invoices | ✅ Sequential tests | Family 2c |
| R-15 Arithmetic tolerance | ✅ $0.01 | Cumulative tests |
| R-18 Edge cases | ✅ 4 families | test_edge_cases.py |

## Conclusion

**Overall compliance:** HIGH — core assignment requirements are met.
**Gaps identified:** 5 enhancement opportunities, none blocking core workflow.
**Recommendation:** Address Gap 3 (columnar PDF) as it affects user-uploaded SuperStore invoices.
