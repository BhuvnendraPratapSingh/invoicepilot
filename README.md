# InvoicePilot — AP Decision Workbench

> AI helps interpret the document. Explicit financial controls decide what may proceed.
> Every decision points to evidence, and unresolved uncertainty has an actionable next step.

InvoicePilot processes vendor PDF invoices through a deterministic pipeline: extract → validate → match → decide. It demonstrates how document AI and rule-based financial controls work together in an accounts payable workflow.

**This is a demo system.** No payment is executed. Not production-ready, certified, fraud-proof, or legally compliant.

## Quick Start

### Prerequisites
- Python 3.11+ (tested with 3.13)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) or pip
- Optional: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for scanned PDFs

### Setup

```bash
# Create virtual environment
uv venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Copy environment config
cp .env.example .env

# Generate PDF fixtures
python scripts/generate_fixtures.py

# Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser.

### Demo Reset

To restore the clean demo baseline (all processing history removed):

```bash
# Via API:
curl -X POST http://127.0.0.1:8000/api/demo/reset

# Or use the "Reset Demo Baseline" button on the dashboard
```

## Running Tests

```bash
# Start the server first, then:
python scripts/test_edge_cases.py
```

This runs 28 integration tests covering the happy path and all four edge-case families.

## Architecture

- **Stack**: Python, FastAPI, SQLAlchemy, SQLite, Jinja2, vanilla JS
- **PDF**: PyMuPDF (text extraction + page rendering), Tesseract (OCR for scans)
- **Fixtures**: ReportLab + Pillow (genuine synthetic PDF generation)
- **Money**: All amounts in integer cents (Decimal for calculations)
- **Policy**: Deterministic `demo-policy-v1`, no ML in the decision path

See [docs/architecture.md](docs/architecture.md) for details.

## What It Does

1. **Receives** a PDF, validates format/size, calculates SHA-256
2. **Detects** byte-level repeats (idempotent)
3. **Extracts** text per page (native + OCR for scanned pages)
4. **Parses** structured invoice fields with provenance
5. **Validates** completeness, dates, currency, arithmetic
6. **Resolves** vendor against approved master (tax ID or exact name)
7. **Detects** business duplicates and identity collisions
8. **Matches** purchase orders (explicit reference or candidate search)
9. **Evaluates** cumulative budget policy (net vs PO capacity)
10. **Commits** decision and reservation atomically
11. **Publishes** evidence, explanation, and next action

## Decisions

| Decision | Meaning |
|---|---|
| AUTO_APPROVED | All controls pass. PO capacity reserved. No payment executed. |
| NEEDS_REVIEW | Ambiguity or policy exception. Human action required. |
| NEEDS_INFORMATION | Required document fact is absent. Vendor must provide corrected document. |
| BLOCKED | Confirmed control prohibition (e.g., duplicate of approved invoice). |

## Four Edge-Case Families

1. **Duplicates**: Byte repeat (idempotent), business duplicate (BLOCKED), identity collision (NEEDS_REVIEW)
2. **Cumulative Budget**: Split invoicing against a PO with tolerance. $10 over ceiling blocks; $10 under passes.
3. **Ambiguous PO**: No PO reference with two plausible candidates. Reviewer selects and re-evaluates.
4. **Scanned/Missing Number**: Image-only PDF, OCR, genuinely absent invoice number → NEEDS_INFORMATION → corrected revision.

See [docs/edge-cases.md](docs/edge-cases.md) for exact inputs and expected outcomes.

## Key Limitations

- USD only. Non-USD routes to review.
- Two-way match (invoice ↔ PO). Receipt of goods/services not verified.
- No authentication (demo actor labels only)
- No payment execution, ERP posting, or real email
- Audit is append-only by application behavior, not cryptographically enforced
- Local extraction handles a constrained layout family, not arbitrary invoices
- OCR requires Tesseract system installation

## Documentation

- [docs/process-map.md](docs/process-map.md) — Pipeline stages and human handoffs
- [docs/assumptions.md](docs/assumptions.md) — Scope, definitions, and limitations
- [docs/build-plan.md](docs/build-plan.md) — Implementation milestones
- [docs/edge-cases.md](docs/edge-cases.md) — Exact inputs and expected outcomes
- [docs/demo-script.md](docs/demo-script.md) — Five-minute recording script
- [docs/interview-notes.md](docs/interview-notes.md) — Key design decision explanations
