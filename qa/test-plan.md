# QA Test Plan — InvoicePilot

## Implementation Stack (Discovered)
- Python 3.13.2, FastAPI, SQLAlchemy 2.x, SQLite (WAL mode)
- Jinja2 templates, vanilla JS/CSS (no Node build)
- PyMuPDF for text extraction/page rendering
- pytesseract (optional, Tesseract OCR)
- ReportLab + Pillow for fixture generation
- Server: uvicorn, single process

## Startup Method
```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## QA Isolation Strategy
- **Port**: 8111 (dev on 8000 left untouched)
- **Database**: `sqlite:///./data/qa_test.db` (separate from `data/invoicepilot.db`)
- **Uploads**: `./data/qa_uploads` (separate from `data/uploads`)
- **Environment**: Set via env vars before starting QA server process
- **Reset**: via `POST /api/demo/reset` endpoint between test groups

## Financial Policy Under Test (demo-policy-v1)
- Currency: USD only
- Arithmetic tolerance: $0.01 (1 cent)
- PO overage: min(PO_net × 1%, $50.00), rounded half-up to cents
- Tolerance cumulative per PO, not per invoice
- Money in integer cents, Decimal for calculations
- Net comparison: invoice_net vs PO capacity (never gross vs net PO)
- Approval creates one active commitment; non-approval creates none

## Seed Baseline
- 5 vendors (V-001 through V-005; V-004 is INACTIVE)
- 6 POs (PO-1001 through PO-1006)
- 2 seed commitments: $6,000 on PO-1002, $2,000 on PO-1003

## Test Scope
| ID | Category | Scenarios |
|---|---|---|
| SM-* | Smoke tests | Startup, health, endpoints, fixture gen |
| HP-* | Happy path | Full pipeline, reservation, evidence |
| DUP-* | Duplicates | Byte repeat, business dup, collision, cross-vendor |
| CUM-* | Cumulative budget | Tolerance boundary, sequential, exact ceiling |
| AMB-* | Ambiguous PO | Review flow, PO selection, capacity re-check |
| SCN-* | Scanned/missing | OCR, missing fields, revision flow |
| FIN-* | Financial validation | Arithmetic, net/gross, dates, currency |
| META-* | Metamorphic | Filename independence, content sensitivity |
| CONC-* | Concurrency | Parallel PO reservation, duplicate race |
| ERR-* | Error handling | Bad files, injection, limits |
| UI-* | Browser/dashboard | Counts, display, export, reset |

## Known Scope Limitations
- Tesseract OCR may not be installed (scanned PDF tests may BLOCK)
- No Playwright browser driver expected (browser tests via API + manual)
- Docker build not tested in this QA pass
- AI-assisted extraction not tested (no API key, by design)
