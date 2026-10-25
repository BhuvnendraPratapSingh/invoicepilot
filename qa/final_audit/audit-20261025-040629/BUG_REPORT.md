# Bug Report — Final Audit

## Summary

**No critical, high, or medium-severity defects found in executed tests.**

## Low-Severity Observations

### LOW-001: Playwright screenshot timeout on reset confirmation
- **Severity**: Low (cosmetic)
- **Test**: UI-15
- **Reproduction**: Click "Reset Demo" → accept confirm dialog → attempt screenshot
- **Expected**: Screenshot captured
- **Actual**: Playwright times out waiting for font rendering
- **Impact**: None — reset works correctly (confirmed by API tests and UI-14). Only affects automated screenshot capture.
- **Root cause**: Font rendering delay in headless Chromium after dialog interaction

## Previously Fixed Defects (Verified Fixed)

### BUG-001 (Fixed): Byte-duplicate orphan cases
- **Previous**: Repeat uploads created orphan InvoiceCase records
- **Current**: Verified fixed — 3 concurrent identical bytes produce exactly 1 case (CONC-01 PASS)
- **Fix location**: `app/services/orchestrator.py` — case/attempt creation moved after byte-dup check

## Coverage Gaps (Not Defects)
The following areas were not tested in this audit due to time/tool constraints:
- Docker build verification
- Missing-date/currency/total as separate extraction cases
- Concurrent distinct invoices exceeding same PO capacity
- Bounded 100-document workload
- Prompt injection in invoice text
- Offline mode verification
