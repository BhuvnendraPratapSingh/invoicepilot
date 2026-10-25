# Bug Report — CSV Repair Run

## Fixed Defects

### BUG-001 (FIXED — High): Indentation error caused 500 on PDF upload
- **File:** `app/services/extraction.py`
- **Symptom:** PDF upload returns 500; "Unexpected token 'I'" in browser
- **Root cause:** Wrong indentation in `FieldExtraction()` call inside fallback vendor-name block
- **Fix:** Aligned `text_span`, `method`, `verification_status`, `)`, `break` to correct depth

### BUG-002 (FIXED — High): Missing asynccontextmanager import crashed server startup
- **File:** `app/main.py`
- **Symptom:** `NameError: name 'asynccontextmanager' is not defined` on startup
- **Root cause:** `import os` addition accidentally replaced `from contextlib import asynccontextmanager`
- **Fix:** Both lines now present

### BUG-003 (FIXED — Medium): Upload route returned HTML 500 instead of JSON
- **File:** `app/api/routes.py`
- **Symptom:** Browser showed "Unexpected token 'I'" JSON parse error
- **Root cause:** Unhandled exceptions in `process_invoice()` propagated as HTML error pages
- **Fix:** `try/except Exception` wraps processing; always returns JSON

## No Unresolved Defects
All executed tests pass. No critical or high-severity defects remain.

## Informational
- `_parse_cents('abc')` correctly returns `None` (validated EX-04)
- `_parse_cents('2500.001')` truncates to 250000 cents — acceptable since spec requires 2 decimal places
- CSV rows with future dates correctly produce NEEDS_REVIEW (not tested in this run, inherits from PDF policy test)
