# InvoicePilot — Live Demo Runbook

## Pre-Demo Setup

```bash
# 1. Ensure virtual environment is active
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/Mac

# 2. Generate fixtures (if not already done)
python scripts/generate_fixtures.py

# 3. Start server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. Open browser
# http://127.0.0.1:8000

# 5. Reset to clean baseline
# Click "Reset Demo Baseline" button on dashboard
# Or: curl -X POST http://127.0.0.1:8000/api/demo/reset
```

## Demo Sequence

### Tab 1: Dashboard (http://127.0.0.1:8000)
Show empty metrics. Point out the demo date badge.

### Step 1: Happy Path
1. Click "Select PDF" → upload `happy_path_apex_invoice.pdf`
2. Watch stage timeline fill in (real events, not fake progress)
3. See AUTO_APPROVED badge
4. Note: $2,500 reservation on PO-1001
5. PDF preview on left, extracted fields on right
6. Scroll to rules — all 8 PASS

### Step 2: Cumulative Budget
1. Go back to dashboard
2. Upload `cumulative_b_meridian.pdf`
3. Show NEEDS_REVIEW
4. Explain the math: $6,000 + $4,060 = $10,060 > $10,050 ceiling
5. Show budget breakdown panel

### Step 3: Ambiguous PO
1. Dashboard → upload `ambiguous_po_brightwave.pdf`
2. Show NEEDS_REVIEW / PO_AMBIGUOUS
3. Two candidate POs visible
4. Enter PO-1005 and reason "Service matches pipeline development scope"
5. Click Re-evaluate
6. Show AUTO_APPROVED after review

### Step 4: Scanned/Missing Number
1. Dashboard → upload `scanned_missing_number_pinnacle.pdf`
2. Show NEEDS_INFORMATION
3. "Invoice number genuinely absent — we don't guess"
4. Upload `scanned_corrected_pinnacle.pdf` as revision
5. Show corrected version processed

### Step 5: Dashboard & Audit
1. Return to dashboard
2. Show 4+ cases with varied decisions
3. Click any case → Export audit JSON
4. "Complete evidence trail without opening the app"

## Failure Recovery

- **Server crash**: Restart with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Interrupted runs are marked on startup.
- **Wrong fixture uploaded**: Use dashboard reset button
- **Port conflict**: Kill process on port 8000, restart
- **OCR not available**: Scanned PDFs will show NEEDS_INFORMATION (graceful fallback). Mention this as a known limitation.

## Offline Mode

Everything works without internet after initial `pip install`. No external API calls in default mode. The demo date is fixed at 2026-03-15 for reproducibility.

## Expected Checkpoints

| Step | Expected Decision | Key Evidence |
|---|---|---|
| Happy Path | AUTO_APPROVED | 8 rules PASS, $2,500 reservation |
| Cumulative B | NEEDS_REVIEW | $10,060 > $10,050 ceiling |
| Ambiguous PO | NEEDS_REVIEW → AUTO_APPROVED | 2 candidates, reviewer selects |
| Scanned | NEEDS_INFORMATION → AUTO_APPROVED | Missing invoice #, corrected revision |
