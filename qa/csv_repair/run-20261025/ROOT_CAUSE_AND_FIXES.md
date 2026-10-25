# Root Cause and Fixes — CSV Repair

## Build Identity
- No git repo. File hashes recorded at audit start.
- Server: port 8000, database `data/invoicepilot.db`
- Test clock: demo business date 2026-03-15
- Audit run: 2026-10-25

## Reported Symptoms
1. "Upload failed: Unexpected token 'I', 'Internal S'... is not valid JSON" on PDF upload
2. Server returning 500 with HTML body instead of JSON
3. Stuck "Processing" cases in dashboard

## Confirmed Root Causes

### ROOT CAUSE 1 (CONFIRMED): Indentation error in extraction.py
**File:** `app/services/extraction.py`
**Symptom:** PDF upload returns 500 / HTML error page
**Cause:** During the vendor-name extraction fix, the `FieldExtraction(...)` closing `)` and `break` were indented at the wrong level inside the fallback `for` loop. Python parses this as valid syntax but raises `IndentationError` at runtime when the fallback code path executes, causing an unhandled exception and a 500 response.
**Before:**
```python
                    result.vendor_name = FieldExtraction(
                        ...
                        page_number=1,
                    text_span=line,       # <-- wrong indentation
                    method=...,
                )                         # <-- wrong indentation
                break                     # <-- wrong indentation
```
**After:**
```python
                    result.vendor_name = FieldExtraction(
                        ...
                        page_number=1,
                        text_span=line,   # <-- fixed
                        method=...,
                    )                     # <-- fixed
                    break                 # <-- fixed
```
**Fix applied:** `app/services/extraction.py` — aligned indentation in fallback vendor name block.

### ROOT CAUSE 2 (CONFIRMED): Missing import in main.py
**File:** `app/main.py`
**Symptom:** Server fails to start with `NameError: name 'asynccontextmanager' is not defined`
**Cause:** Adding `import os` via str_replace inadvertently removed the existing `from contextlib import asynccontextmanager` line.
**Fix applied:** Restored `from contextlib import asynccontextmanager` alongside `import os`.

### ROOT CAUSE 3 (CONFIRMED): Upload route not catching all exceptions
**File:** `app/api/routes.py`
**Symptom:** When the server was in a broken state, unhandled exceptions propagated as 500 HTML pages, and the JavaScript `resp.json()` failed with "Unexpected token 'I'" (HTML "Internal Server Error").
**Fix applied:** Wrapped `process_invoice()` call in `try/except Exception` that always returns a JSON response. JavaScript `uploadFile()` now checks `content-type` before calling `.json()`.

## CSV Feature Status
The CSV invoice import feature is **working correctly**. After the above fixes:
- CSV upload processes rows through the full financial pipeline
- Financial rules (vendor resolution, PO matching, budget checks, arithmetic) work identically to PDF
- Duplicate detection works cross-format (PDF original + CSV same identity → IDENTITY_COLLISION)
- Arithmetic mismatch rows are rejected (subtotal+tax ≠ gross → NEEDS_REVIEW)
- Unknown vendors cannot auto-approve
- Over-budget rows create no commitment

## Files Changed
| File | Change |
|---|---|
| `app/services/extraction.py` | Fixed indentation in fallback vendor name block |
| `app/main.py` | Restored `from contextlib import asynccontextmanager` |
| `app/api/routes.py` | Added `try/except` in upload route + CSV endpoint added |
| `app/static/dashboard.js` | Added CSV upload handler + content-type check in PDF handler |
| `app/templates/dashboard.html` | Added CSV upload button and results panel |
| `app/services/csv_processor.py` | **New file** — CSV invoice processing service |

## No Financial Policy Changes
All changes are presentation-layer (HTML/JS), error-handling, or the new CSV feature. No change to:
- Decimal/integer-cent arithmetic
- PO capacity checks
- Duplicate detection logic
- Commitment creation rules
- Policy thresholds
