# Regression Report

## Commands Executed
```powershell
# Existing regression suite (port 8000)
python scripts/test_edge_cases.py

# New CSV diagnostic
python qa/csv_repair/run-20261025/tests/diagnose.py

# New CSV extended checks
python qa/csv_repair/run-20261025/tests/extended_checks.py
```

## Results Summary

| Suite | Tests | Pass | Fail | Blocked |
|---|---|---|---|---|
| Existing edge cases | 28 | 28 | 0 | 0 |
| CSV diagnostic | 19 | 19 | 0 | 0 |
| CSV extended checks | 15 | 15 | 0 | 0 |
| **Total** | **62** | **62** | **0** | **0** |

## Financial Controls Verified

| Check | Method | Result |
|---|---|---|
| Net vs gross PO comparison | D1-03, D3-01 | PASS |
| Exact ceiling $4,050 passes | D3-01 | PASS |
| $4,050.01 fails and no commitment | D3-02, D3-03 | PASS |
| Arithmetic mismatch rejected | EX-01/02/03 | PASS |
| Unknown vendor rejected | D5-03/04 | PASS |
| Overage $50 cap | EX-05/06/07 | PASS |
| Cross-format duplicate | EX-08/09/10 | PASS |
| Original commitment unchanged | EX-10 | PASS |

## Coverage Gaps

| Area | Status | Notes |
|---|---|---|
| Sequential CSV $4,040 then $20 | NOT RUN | Covered by existing test_edge_cases.py |
| Concurrent CSV uploads | NOT RUN | Not run with overlapping HTTP requests |
| >1000 row CSV | NOT RUN | Bounded by 2MB limit |
| CRLF vs LF | NOT RUN | Standard Python csv handles both |
| Browser-level CSV upload | NOT RUN | Playwright test not added for CSV path |
| Docker build | NOT RUN | Dockerfile present, not tested |
