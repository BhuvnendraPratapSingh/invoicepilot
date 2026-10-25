# InvoicePilot — Verification Report

## Environment
- Python 3.13.2 on Windows
- uv package manager
- SQLite (via SQLAlchemy 2.x)
- PyMuPDF for PDF handling
- Tesseract OCR: NOT installed on test machine (scanned tests use graceful fallback)

## Tests Run

### API Smoke Test (`scripts/test_api.py`)
- ✅ Health check returns OK
- ✅ Dashboard returns empty baseline
- ✅ Fixtures list returns 10 items
- ✅ Happy path upload → AUTO_APPROVED with $2,500 reservation

### Edge Case Integration Tests (`scripts/test_edge_cases.py`)
28/28 passing:

**Happy Path (7/7)**
- ✅ AUTO_APPROVED, ALL_CHECKS_PASSED
- ✅ Net $2,500.00, Gross $2,700.00
- ✅ PO-1001 matched, commitment created

**Edge Family 1: Duplicates (5/5)**
- ✅ Identical bytes → byte duplicate detected (idempotent)
- ✅ Reissued duplicate → BLOCKED / DUPLICATE_INVOICE
- ✅ Identity collision → NEEDS_REVIEW / INVOICE_IDENTITY_COLLISION

**Edge Family 2: Cumulative Budget (6/6)**
- ✅ A ($4,040 net, projected $10,040) → AUTO_APPROVED with warning
- ✅ B ($4,060 net, projected $10,060) → NEEDS_REVIEW / PO_CUMULATIVE_LIMIT_EXCEEDED
- ✅ Sequential A+C → NEEDS_REVIEW (cumulative tolerance, not per-invoice)

**Edge Family 3: Ambiguous PO (5/5)**
- ✅ NEEDS_REVIEW / PO_AMBIGUOUS
- ✅ Two PO candidates found
- ✅ Reviewer selects PO → re-evaluation → AUTO_APPROVED

**Edge Family 4: Scanned/Missing Number (5/5)**
- ✅ NEEDS_INFORMATION / MISSING_INVOICE_NUMBER (without OCR)
- ✅ Corrected revision → processed and approved

## Verified Behaviors
- PDF text extraction reads actual document content (not fixture filenames)
- Budget arithmetic uses Decimal, not floating point
- Overage tolerance: min(PO_net × 1%, $50), cumulative
- Duplicate detection: separate byte-level and business-identity layers
- Re-evaluation creates new attempt, preserves original evidence
- Demo reset restores clean baseline

## Known Limitations / Unverified
- Tesseract OCR not available on test machine — scanned PDF test uses graceful fallback
- Concurrent PO reservation test not automated (SQLite serialized writes provide basic safety)
- Playwright browser tests not implemented
- Docker build not tested (Dockerfile provided)
- AI-assisted extraction not tested (requires API key)
- No load/stress testing

## Not Implemented
- Docker verification
- Playwright browser smoke test
- Concurrent duplicate approval test
- AI-assisted extraction mode
- Email/EML ingestion
