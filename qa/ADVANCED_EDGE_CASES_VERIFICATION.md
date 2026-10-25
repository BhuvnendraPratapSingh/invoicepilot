# Advanced Edge Cases — Verification Report

## Build & Environment
- QA server: port 8111, database `data/qa_test.db`, storage `data/qa_uploads`
- Tesseract OCR 5.4.0 available
- Demo server on port 8000 untouched
- Test timestamp: 2026-10-25

## Results: 34 PASS, 0 FAIL, 0 BLOCKED

### Scenario A: Stale Review (8/8 PASS)
| Test | Expected | Actual | Status |
|---|---|---|---|
| A-01 | Invoice A (no PO ref) → NEEDS_REVIEW/PO_AMBIGUOUS | NEEDS_REVIEW/PO_AMBIGUOUS | PASS |
| A-02 | Invoice A has 0 commitments | 0 | PASS |
| A-03 | Invoice B ($200, PO-1002) → AUTO_APPROVED | AUTO_APPROVED | PASS |
| A-04 | Invoice B creates $200 commitment | 1 × 20000 cents | PASS |
| A-05 | Stale resolution sees $6,200 committed → NEEDS_REVIEW | NEEDS_REVIEW/PO_CUMULATIVE_LIMIT_EXCEEDED | PASS |
| A-06 | Invoice A still 0 commitments after review | 0 | PASS |
| A-07 | Review action recorded | SELECT_PO action present | PASS |
| A-08 | Case has ≥2 processing attempts | ≥2 | PASS |

### Scenario B: Correction After Approval (7/7 PASS)
| Test | Expected | Actual | Status |
|---|---|---|---|
| B-01 | Original ADV-CORR-1042 → AUTO_APPROVED | AUTO_APPROVED | PASS |
| B-02 | Original commitment = $2,000 | 1 × 200000 cents | PASS |
| B-03 | Correction (different amount) → IDENTITY_COLLISION | NEEDS_REVIEW/INVOICE_IDENTITY_COLLISION | PASS |
| B-04 | Original commitment unchanged | 1 × 200000 cents | PASS |
| B-05 | Correction case has 0 commitments | 0 | PASS |
| B-06 | Re-upload correction → byte duplicate | is_byte_duplicate=True | PASS |
| B-07 | Re-upload original → byte duplicate | is_byte_duplicate=True | PASS |

### Scenario C: PO Belongs to Another Vendor (4/4 PASS)
| Test | Expected | Actual | Status |
|---|---|---|---|
| C-01 | Apex invoice citing Meridian's PO → NOT approved | NEEDS_REVIEW | PASS |
| C-02 | No commitment created | 0 | PASS |
| C-03 | PO matching explains vendor mismatch | "PO 'PO-1002' belongs to vendor V-002, not V-001" | PASS |
| C-04 | Control: same vendor's PO → AUTO_APPROVED | AUTO_APPROVED | PASS |

### Scenario D: OCR with Distractor Identifiers (9/9 PASS)
| Test | Expected | Actual | Status |
|---|---|---|---|
| D-01 | Fixture has <50 chars native text | <50 (image-only) | PASS |
| D-02 | OCR produces a business decision | NEEDS_INFORMATION | PASS |
| D-03 | Invoice number stays null (distractors not used) | None | PASS |
| D-04 | Decision = NEEDS_INFORMATION/MISSING_* | NEEDS_INFORMATION/MISSING_INVOICE_NUMBER | PASS |
| D-05 | No commitment | 0 | PASS |
| D-06 | PO reference correctly extracted | PO-1003 | PASS |
| D-07 | Corrected revision processed | Decision returned | PASS |
| D-08 | Corrected version extracts real invoice number | PCS-ADV-2026-0099 | PASS |
| D-09 | History preserved (≥2 attempts) | ≥2 | PASS |

### Regression: Original 4 Edge Cases (6/6 PASS)
| Test | Status |
|---|---|
| REG-01 Happy path → AUTO_APPROVED | PASS |
| REG-02 Reissued duplicate → BLOCKED | PASS |
| REG-03 Cumulative A → AUTO_APPROVED | PASS |
| REG-04 Cumulative B → NEEDS_REVIEW | PASS |
| REG-05 Ambiguous PO → NEEDS_REVIEW | PASS |
| REG-06 Scanned missing# → NEEDS_INFORMATION | PASS |

## What Already Worked vs What Changed

### Already worked — needed only tests
1. **Stale review detection** — `_get_committed_cents()` in policy_engine.py queries live DB during re-evaluation. No cached balances.
2. **Identity collision on correction** — `check_business_duplicate()` correctly detects same-vendor+invoice# with different amounts and returns IDENTITY_COLLISION.
3. **Vendor/PO ownership validation** — `match_po()` checks `po.vendor_id != vendor_id` on explicit PO references and rejects mismatches.
4. **OCR distractor handling** — Extraction patterns specifically require "Invoice" prefix for invoice numbers. PO numbers, account numbers, and service references use separate patterns.

### Changed
| File | Change | Reason |
|---|---|---|
| `data/seed/purchase_orders.csv` | Added PO-1007 ($8,000, V-002) | Create genuine 2-PO ambiguity for Scenario A |
| `scripts/generate_advanced_fixtures.py` | New file — 7 PDF fixtures | Test fixtures for scenarios A-D |
| `qa/tests/test_advanced_edge_cases.py` | New file — 34 tests | Comprehensive test suite |

### Zero application logic changes
No modifications to orchestrator.py, policy_engine.py, po_matching.py, duplicate_detection.py, extraction.py, routes.py, or any template/CSS.

## Approved-Liability Replacement
**Deliberately unsupported.** When a correction arrives for an already-approved invoice (Scenario B), the system detects the identity collision and produces NEEDS_REVIEW. It does NOT:
- Auto-approve the new amount
- Replace the original commitment
- Release the original approval

This is by design. Replacing an approved liability requires manual AP resolution outside this demo scope.

## Evidence
- `qa/evidence/advanced_edge_cases/a04_invoice_b.json` — Invoice B case detail
- `qa/evidence/advanced_edge_cases/a05_stale_resolution.json` — Stale review resolution result
- `qa/evidence/advanced_edge_cases/a07_full_case_a.json` — Complete case A with all attempts
- `qa/evidence/advanced_edge_cases/b03_correction_result.json` — Correction collision result
- `qa/evidence/advanced_edge_cases/c03_wrong_vendor.json` — Vendor/PO mismatch case
- `qa/evidence/advanced_edge_cases/d02_ocr_result.json` — OCR extraction with distractors
- `qa/evidence/advanced_edge_cases/d08_corrected.json` — Corrected OCR case
- `qa/advanced_results.json` — Structured test results
