# Demo Readiness

## Verdict: READY WITH CAVEATS

## Core workflows verified:
- ✅ PDF upload → all 4 edge case families (28/28)
- ✅ CSV upload → invoice import with financial controls (34/34 new tests)
- ✅ Financial controls identical for PDF and CSV inputs
- ✅ No orphan cases, no duplicate commitments
- ✅ Server starts cleanly, no import errors
- ✅ All HTML pages load, all status badges render

## Caveats:
- Browser-level Playwright test for CSV upload not executed (API confirmed working)
- Concurrent CSV upload race conditions not tested with overlapping requests
- Docker build not verified in this run

## Startup Instructions
```powershell
cd c:\Users\bhsingh2401\Downloads\ned\Trans\companies\Zamp
# Double-click start.bat  OR:
.venv\Scripts\activate
$env:PATH="C:\Users\$env:USERNAME\AppData\Local\Programs\Tesseract-OCR;"+$env:PATH
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000
```

## Pre-Demo Checklist
- [ ] Server starts and shows "✓ Database already populated" or "✓ Seed data loaded"
- [ ] http://127.0.0.1:8000 shows dashboard with Upload PDF + Upload CSV buttons
- [ ] Health page shows OCR: Tesseract 5.4
- [ ] Click Reset Demo → confirm → 0 cases, $0.00 approved

## Verified Demo Sequence
1. PDF happy path → AUTO_APPROVED
2. CSV upload (Apex + Meridian rows) → decisions per row
3. Scanned PDF → NEEDS_INFORMATION → corrected revision
4. Cumulative budget → NEEDS_REVIEW

## Note on Demo DB
The ordinary demo database (`data/invoicepilot.db`) was not modified during this audit.
To verify it is running the current code, restart using `start.bat`.
