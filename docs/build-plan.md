# InvoicePilot — Build Plan

## Milestone 1: Executable Happy-Path Vertical Slice

### Deliverables
1. Project skeleton with all directories
2. SQLite database models (vendor, PO, invoice_case, processing_attempt, etc.)
3. Seed data import from CSV (vendors, POs, prior commitments)
4. PDF fixture generation (happy path invoice)
5. PDF reception and validation
6. Text extraction (native PyMuPDF)
7. Local pattern-based field extraction
8. Field validation and arithmetic checks
9. Vendor resolution (exact match)
10. PO matching (explicit reference)
11. Financial policy evaluation with reservation
12. Minimal upload UI and detail view
13. First integration test

### Verification
- Server starts and serves upload page
- Upload happy-path PDF → AUTO_APPROVED with $2,500.00 reservation
- Integration test passes

## Milestone 2: Four Edge-Case Families

### Edge Case 1: Duplicates
- Identical bytes → idempotent (link to original)
- Same business identity + same amounts → BLOCKED
- Same identity + different amounts → NEEDS_REVIEW (collision)
- PDF fixtures + tests

### Edge Case 2: Cumulative Tolerance
- Split invoicing against $10,000 PO with $6,000 prior commitment
- Invoice A ($4,040 net) → AUTO_APPROVED with tolerance warning
- Invoice B ($4,060 net) → NEEDS_REVIEW (exceeds by $10)
- Sequential A then C ($20 net) → NEEDS_REVIEW
- PDF fixtures + tests

### Edge Case 3: Ambiguous PO
- Two plausible POs, no PO reference on invoice
- → NEEDS_REVIEW with candidate evidence
- Reviewer selects PO → re-evaluate
- PDF fixture + review flow + tests

### Edge Case 4: Scanned/Missing Invoice Number
- Image-only PDF (no text layer)
- OCR runs, vendor and amounts extracted
- Invoice number genuinely absent → NEEDS_INFORMATION
- Corrected PDF revision flow
- PDF fixtures + tests

## Milestone 3: Observable, Usable UI

### Dashboard
- Upload + fixture downloads
- Real counts and metrics
- Invoice table with search/filter
- Empty/loading/error states

### Live Run View
- Stage timeline with events
- PDF preview + evidence panel
- Decision display with explanation
- Reconciliation breakdown

### Review Workspace
- PO selection with reason
- Field correction with evidence
- Corrected PDF attachment
- Re-evaluation flow

### Health & Diagnostics
- Dependency health checks
- Demo reset with confirmation
- Fixture library

## Milestone 4: Hardening & Demo Prep

### Technical
- Concurrency tests (PO capacity, duplicate approval)
- Error behavior coverage
- Browser smoke test
- Docker setup verification

### Documentation
- Complete README
- Architecture doc
- Edge cases doc
- Demo script (≤5 min)
- Live demo runbook
- Interview notes
- Verification report
- AI usage doc

## Tech Stack
- Python 3.11+, FastAPI, Pydantic, SQLAlchemy, SQLite
- Jinja2 templates, vanilla CSS/JS (no Node build)
- PyMuPDF (text extraction + page rendering)
- pytesseract + Tesseract (OCR for scanned pages)
- ReportLab + Pillow (synthetic PDF generation)
- pytest (tests)
- Optional: Anthropic API for AI-assisted extraction

## Timeline Priority
If behind: cut optional AI extraction, charting, polish.
Never cut: genuine OCR, live stages, auditability, edge-case tests.
