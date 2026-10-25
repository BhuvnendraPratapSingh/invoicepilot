# InvoicePilot — Architecture

## Stack
- **Python 3.11+** with FastAPI (async web framework)
- **SQLAlchemy 2.x** ORM with **SQLite** (WAL mode, FK enforcement, busy timeout)
- **Jinja2** server-side templates with vanilla CSS and JS
- **PyMuPDF** (`fitz`) for native PDF text extraction and page rendering
- **pytesseract** + Tesseract OCR for scanned/image-only pages
- **ReportLab + Pillow** for synthetic PDF fixture generation

## Data Model

```
vendors ──────────── vendor_aliases
   │
purchase_orders ──── commitments ──── decisions
   │                     │                │
   └── invoice_cases ────┤           processing_attempts
                         │                │
                    source_documents  stage_events
                                         │
                                    extracted_data ── field_evidences
                                         │
                                    rule_results
                                         │
                                    review_actions
```

### Key Entities
- **InvoiceCase**: One per unique business invoice. Holds current decision state.
- **SourceDocument**: PDF file with SHA-256. Multiple revisions per case.
- **ProcessingAttempt**: One run through the pipeline. Multiple per case (upload, review, revision).
- **StageEvent**: Start/complete/fail/skip for each of 11 stages.
- **ExtractedData**: Structured fields from one attempt.
- **FieldEvidence**: Per-field provenance (page, span, method, verification status).
- **RuleResult**: Individual rule pass/fail with observed vs expected.
- **Decision**: Business outcome with policy snapshot and evidence.
- **Commitment**: Budget reservation against a PO. One active per case.
- **ReviewAction**: Human intervention record with before/after values.

## Transaction Strategy

Financial reservations use SQLAlchemy/SQLite transactions:
1. Decision and commitment are written in the same `db.commit()`
2. Before committing, re-check PO exposure inside the transaction
3. `UniqueConstraint(case_id, po_id)` prevents double reservations
4. WAL mode + busy timeout handle concurrent readers/writers

This is demo-level isolation. Production would use PostgreSQL with `SELECT ... FOR UPDATE`.

## Money Handling

All monetary values stored as integer cents. `Decimal` used for calculations.
Never binary floating-point.

```
invoice_net = subtotal - discount + shipping
invoice_gross = net + tax
po_capacity = po_net + min(po_net * 0.01, $50.00) - sum(active_commitments)
```

## Processing Pipeline

11 stages with persisted events. Failed stages block dependents but independent checks continue.

1. Receive & Validate PDF (size, pages, format)
2. Byte-Level Duplicate Check (SHA-256)
3. Text Extraction (native + OCR per page)
4. Field Extraction (local regex or optional AI)
5. Field Validation (completeness, dates, currency)
6. Vendor Resolution (tax ID → exact name → alias → fuzzy)
7. Business Duplicate Detection (vendor + invoice number identity)
8. PO Matching (explicit ref or candidate search)
9. Financial Policy Evaluation (all rules, cumulative budget)
10. Commit Decision & Reservation (atomic)
11. Publish Results

## Extraction Modes

### Local (default, no API key)
Pattern-based extraction from document text using regex. Handles three distinct vendor layouts with varied label positions. Extraction is separate from policy — patterns read the document, rules evaluate the result.

### AI-Assisted (optional)
Sends extracted text to Anthropic structured-extraction adapter. Validates response against schema. Stores prompt version, model ID, and token usage. Falls back to local on failure.

## Deliberate Exclusions
- No Redis, Kubernetes, or microservices
- No Node.js build toolchain
- No authentication system
- No payment or ERP integration
- No complex policy editor UI
