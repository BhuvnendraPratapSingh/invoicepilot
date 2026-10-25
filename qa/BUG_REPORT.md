# InvoicePilot — Bug Report

## BUG-001: Byte-duplicate detection creates orphan case record

**Severity**: Medium
**Status**: Confirmed, Reproducible
**Affected Tests**: DUP-02, DASH-01, SM-05 (cascade)

### Description
When the same PDF file is uploaded twice, the orchestrator creates a new `InvoiceCase` and `ProcessingAttempt` record *before* the byte-level duplicate check runs. When the duplicate is detected, the function returns early with the original case_id, but the orphan case (with `decision=None`, `invoice_number=None`) persists in the database.

### Reproduction
1. Reset to baseline
2. Upload `happy_path_apex_invoice.pdf` → AUTO_APPROVED (case A)
3. Upload same file again → byte_dup=True, returns case A's ID
4. Query `/api/cases` → shows 2 non-seed cases instead of 1
5. Orphan case has decision=None, invoice_number=None

### Evidence
```
Non-seed case count: 2
  73b2eb3b-a1a... decision=None inv=None    ← orphan
  c55732a0-91f... decision=AUTO_APPROVED inv=INV-2026-0451
```

### Impact
- Dashboard `total_cases` count is inflated by orphan cases
- No financial impact (orphan has no commitment)
- Cosmetic issue for demo; does not affect pipeline correctness

### Root Cause
In `orchestrator.py:process_invoice()`, lines ~108-120: case and attempt are created and committed before the byte-dup check at ~130. On byte-dup detection (~140), the function returns without cleaning up the orphan case.

### Recommended Fix
Move case/attempt creation AFTER the byte-duplicate check passes. Only create the case+attempt when processing will actually proceed. Alternatively, delete the orphan case on byte-dup detection return path.

---

## BUG-002: Extraction fails on amounts formatted without decimal places

**Severity**: Low (extraction limitation, not a policy defect)
**Status**: Confirmed
**Affected Tests**: CUM-05

### Description
The extraction regex for money amounts requires two decimal digits: `\$?([\d,]+\.\d{2})`. Amounts formatted as `$4050` (no comma, no decimal) are not extracted. This caused the QA-generated boundary test fixture to fail extraction.

### Impact
The existing fixtures all format amounts correctly (e.g., `$4,050.00`). This only affects QA-generated fixtures and potentially real-world invoices with unusual formatting. Since local extraction is documented as handling "a constrained layout family," this is a known limitation, not a defect.

### Root Cause
`extraction.py:_find_money_value()` requires `\.d{2}` in the money regex.

### Recommendation
Consider accepting integers without decimal points as well: `\$?([\d,]+(?:\.\d{1,2})?)`. But this is optional and may introduce false positives.

---

## No critical or high-severity defects found.
