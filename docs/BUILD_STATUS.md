# InvoicePilot — Build Status

## Current State: Milestones 1-3 Complete

### Milestone 1: Happy-Path Vertical Slice ✅
- Project skeleton with all directories
- SQLite database with full model set
- Seed data import (vendors, POs, historical commitments)
- 10 PDF fixtures generated with ReportLab
- Complete 11-stage processing pipeline
- Local regex-based extraction for 3 vendor layouts
- Vendor resolution, PO matching, duplicate detection
- Deterministic policy engine with cumulative budget
- Upload → AUTO_APPROVED with $2,500 reservation
- Dashboard and case detail UI

### Milestone 2: Four Edge-Case Families ✅
- Edge 1: Byte duplicate, business duplicate (BLOCKED), identity collision (NEEDS_REVIEW)
- Edge 2: Cumulative tolerance A (within), B (exceeds), sequential A+C (cumulative)
- Edge 3: Ambiguous PO → reviewer selects → re-evaluate
- Edge 4: Scanned/missing number → NEEDS_INFORMATION → corrected revision → approved
- 28/28 integration tests passing

### Milestone 3: Observable, Usable UI ✅
- Dashboard with real metrics, upload, search/filter
- Live stage timeline with persisted events
- PDF preview with page images
- Extracted fields with evidence tags
- Rule evaluation display
- Budget reconciliation panel
- Review actions (PO selection, revision upload)
- Fixture library with download
- Health check page
- Demo reset with confirmation
- Audit export (JSON)

### Milestone 4: Hardening & Demo Prep — Partial
- ✅ Documentation complete (README, process-map, assumptions, architecture, edge-cases, demo-script, live-demo-runbook, interview-notes, verification, ai-usage)
- ✅ Dockerfile and compose.yaml provided
- ⚠️ Docker build not verified on this machine
- ⚠️ Tesseract OCR not installed — scanned PDF edge case uses graceful fallback
- ⚠️ Playwright browser tests not implemented
- ⚠️ Concurrent PO reservation test not automated
- ⚠️ AI-assisted extraction mode not tested (no API key)

## Verified Commands

```bash
# Setup
uv venv .venv
uv pip install -r requirements.txt
python scripts/generate_fixtures.py

# Run server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Run tests (with server running)
python scripts/test_edge_cases.py

# Reset demo
curl -X POST http://127.0.0.1:8000/api/demo/reset
```

## Local UI Address
http://127.0.0.1:8000

## Files Created

### Application Code
- app/main.py — FastAPI entry point
- app/config.py — Configuration from .env
- app/db.py — SQLAlchemy engine and session
- app/models/ — Vendor, PO, InvoiceCase, SourceDocument, ProcessingAttempt, etc.
- app/api/routes.py — API endpoints
- app/services/orchestrator.py — 11-stage pipeline
- app/services/extraction.py — Local field extraction
- app/services/pdf_reader.py — PyMuPDF text extraction
- app/services/ocr.py — Tesseract OCR
- app/services/vendor_resolution.py — Vendor matching
- app/services/po_matching.py — PO matching and candidates
- app/services/duplicate_detection.py — Byte and business duplicates
- app/services/policy_engine.py — Deterministic financial rules
- app/services/seed.py — CSV seed data loader
- app/templates/ — Jinja2 HTML templates
- app/static/ — CSS and JavaScript

### Data
- data/seed/vendors.csv, purchase_orders.csv, commitments.csv
- data/fixtures/ — 10 PDF fixtures
- data/expected_results.json — Test-only manifest

### Infrastructure
- requirements.txt, .env.example, Dockerfile, compose.yaml

### Documentation
- README.md + 10 docs/ files

### Tests
- scripts/test_api.py — API smoke test
- scripts/test_edge_cases.py — 28 integration tests
- scripts/generate_fixtures.py — PDF fixture generation
