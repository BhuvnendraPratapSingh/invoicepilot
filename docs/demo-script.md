# InvoicePilot — Demo Script (≤5 minutes)

## Setup Before Recording
1. Server running: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. Reset baseline: click "Reset Demo Baseline" on dashboard
3. Browser at http://127.0.0.1:8000
4. Have fixture PDFs downloaded or accessible

## Recording

### 0:00–0:25 — Introduction
- "This is InvoicePilot, an AP decision workbench"
- Show empty dashboard with metrics
- "It processes vendor invoices: extraction, matching, policy checks, and produces explainable decisions"
- "No money is moved. Every approval reserves PO capacity for AP processing."

### 0:25–1:25 — Happy Path (live)
- Click Upload, select `happy_path_apex_invoice.pdf`
- Watch stage timeline complete in real time
- Show: vendor resolved, PO matched, arithmetic reconciled
- Show the decision: AUTO_APPROVED with all rules passing
- Point out the $2,500 reservation on PO-1001
- Show PDF preview with extracted fields side by side
- Note: "No payment has been executed" disclaimer

### 1:25–2:25 — Cumulative Budget (live)
- Upload `cumulative_b_meridian.pdf`
- Show NEEDS_REVIEW decision
- Explain: "PO-1002 has $10,000 net with $6,000 already committed"
- Show the budget breakdown: projected $10,060 exceeds $10,050 ceiling by $10
- "The 1% or $50 overage is cumulative, not per-invoice"
- Show the recommendation: "Request PO amendment"

### 2:25–3:20 — Ambiguous PO (live)
- Upload `ambiguous_po_brightwave.pdf`
- Show NEEDS_REVIEW / PO_AMBIGUOUS
- "No PO reference on this invoice, two plausible POs"
- Show candidate POs
- Select PO-1005, enter reason, click Re-evaluate
- Show re-evaluation completes with AUTO_APPROVED
- "The reviewer resolved ambiguity; the system still checked all rules"

### 3:20–4:15 — Scanned Missing Number
- Upload `scanned_missing_number_pinnacle.pdf`
- Show NEEDS_INFORMATION
- "Image-only scan. OCR ran. Invoice number genuinely absent."
- Show the information request: "We don't guess or fabricate data"
- Upload corrected version as revision
- Show new evaluation with invoice number PCS-2026-0312
- "Original evidence preserved alongside the correction"

### 4:15–4:45 — Dashboard & Audit
- Return to dashboard, show all cases and metrics
- Show straight-through rate calculation
- Export an audit bundle (JSON)
- "Every decision includes evidence, rules, policy snapshot, and timestamps"

### 4:45–5:00 — Limitations & Next Steps
- "This is a demo — no auth, no payment execution, constrained layouts"
- "Production would add: authentication, durable workers, receipt verification, ERP integration"
- "The core principle holds: AI interprets, rules decide, evidence explains"
