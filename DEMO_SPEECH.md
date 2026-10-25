# InvoicePilot — 5-Minute Demo Speech

---

## PART 1 — Introduction & Dashboard (0:00 – 0:40)

**[Screen: Open dashboard at localhost:8000. Hit "Demo Reset" before starting.]**

Hi everyone. Today I'm going to walk you through InvoicePilot — an AP Decision Workbench that automates vendor invoice processing.

The problem is straightforward. In most finance teams, every invoice that comes in has to be manually reviewed — checking vendor identity, matching purchase orders, verifying amounts, catching duplicates. It's slow, error-prone, and expensive.

InvoicePilot solves this by running every uploaded invoice through an 11-stage processing pipeline. It extracts data from the PDF, resolves the vendor, matches purchase orders, checks for duplicates, evaluates eight financial policy rules, and makes an automated decision — all in seconds.

There are four possible outcomes: Auto-Approved, Needs Review, Needs Information, or Blocked. The goal is to maximize what we call the straight-through processing rate — the percentage of invoices that pass all checks with zero human involvement.

Let me show you how it works.

---

## PART 2 — Happy Path (0:40 – 1:40)

**[Screen: Download "Happy Path" fixture from the Test Fixtures section. Drag `happy_path_apex_invoice.pdf` into the upload zone.]**

Let's start with a clean invoice. This is from Apex Digital Solutions — it has all required fields, an explicit PO reference, and correct amounts.

I'll drag it into the upload zone.

**[Screen: Wait for processing. Case appears in table. Click on the case row to open case detail.]**

And it's Auto-Approved. Let's look at what happened under the hood.

**[Screen: Scroll through the processing timeline — all 11 stages green.]**

Here's the processing timeline — all eleven stages completed successfully. You can see each stage: PDF validation, duplicate check, text extraction, field extraction, vendor resolution, duplicate detection, PO matching, and policy evaluation.

**[Screen: Scroll to Extracted Fields section.]**

The system extracted the vendor name, tax ID, invoice number, dates, currency, PO reference, and all financial amounts — all from regex-based pattern matching on the raw PDF text. No AI API calls needed for this.

**[Screen: Scroll to Policy Evaluation section.]**

All eight policy rules passed. Required fields present, currency is USD, date is valid, vendor is approved and active, no duplicates, PO matched, arithmetic reconciles, and the cumulative budget is within limits.

**[Screen: Scroll to PO Budget Reconciliation.]**

And here's the budget reconciliation — showing the PO amount, what's already committed, what this invoice adds, and how much headroom remains. Everything checks out.

---

## PART 3 — Duplicate Detection (1:40 – 2:30)

**[Screen: Go back to dashboard. Upload `duplicate_original_meridian.pdf`.]**

Now let's test duplicate detection. I'll upload an invoice from Meridian Consulting.

**[Screen: Wait for Auto-Approved. Then upload `duplicate_reissued_meridian.pdf`.]**

That one's approved. Now watch what happens when I upload a reissued version — same vendor, same invoice number, same amounts, but a different PDF file.

**[Screen: Wait for BLOCKED. Click into the case.]**

Blocked. The system detected this as a duplicate invoice. Same vendor ID, same normalized invoice number, same amounts — and there's already an approved case on record. The reason code is DUPLICATE_INVOICE, and the next action tells the reviewer: check the original, no further action needed unless it's a dispute.

This prevents double payments — one of the biggest risks in accounts payable.

---

## PART 4 — Cumulative Budget Control (2:30 – 3:20)

**[Screen: Go back to dashboard. Upload `cumulative_a_meridian.pdf`.]**

Next — cumulative budget control. This PO has a ten-thousand-dollar budget with six thousand already committed. I'm uploading an invoice for four thousand forty dollars.

**[Screen: Wait for Auto-Approved. Click into case, scroll to budget reconciliation.]**

Auto-Approved. The projected total is ten thousand forty — which is over the PO amount, but within the one-percent tolerance. The system allows a small overage of up to fifty dollars or one percent, whichever is less. You can see the tolerance warning right here.

**[Screen: Go back to dashboard. Upload `cumulative_b_meridian.pdf`.]**

Now I'll upload another invoice — this one for four thousand sixty dollars.

**[Screen: Wait for NEEDS_REVIEW. Click into the case.]**

Needs Review. The projected cumulative is now ten thousand sixty — which exceeds the ten thousand fifty ceiling by ten dollars. The system caught it and flagged it for a reviewer. The next action says: request a PO amendment or get a corrected invoice. Every dollar is tracked.

---

## PART 5 — Ambiguous PO & Human Review (3:20 – 4:10)

**[Screen: Go back to dashboard. Upload `ambiguous_po_brightwave.pdf`.]**

Here's an interesting one. This invoice from Brightwave Analytics has no PO reference. The vendor has two open purchase orders, so the system can't decide which one applies.

**[Screen: Wait for NEEDS_REVIEW. Click into case. Scroll to PO Selection panel.]**

Needs Review — reason code PO Ambiguous. But look at this — the system found two PO candidates and is presenting them to the reviewer with remaining budget info for each. The reviewer selects the correct PO, provides a reason...

**[Screen: Select a PO candidate. Type reason: "Confirmed with project manager — this falls under the analytics retainer." Click Submit.]**

...and the system re-evaluates the entire invoice with the selected PO.

**[Screen: Wait for re-evaluation to complete — should show AUTO_APPROVED.]**

Auto-Approved. The human resolved the ambiguity, and the system confirmed everything else checks out. That review action is permanently recorded in the audit trail.

---

## PART 6 — OCR & Revision Flow (4:10 – 4:50)

**[Screen: Go back to dashboard. Upload `scanned_missing_number_pinnacle.pdf`.]**

Last scenario — a scanned document. This is an image-only PDF. The system runs OCR using Tesseract to read the text, but there's a problem: the invoice number is missing from the document entirely.

**[Screen: Wait for NEEDS_INFORMATION. Click into the case.]**

Needs Information — missing invoice number. The system tells the clerk: request the corrected document from the vendor. So the vendor sends a corrected PDF, and I attach it as a revision.

**[Screen: Scroll to Revision Upload panel. Upload `scanned_corrected_pinnacle.pdf` as a revision.]**

The corrected version now includes the invoice number. The system re-processes from scratch...

**[Screen: Wait for AUTO_APPROVED.]**

And it's Auto-Approved. Full audit trail preserved — original submission, the gap, the correction, and the final approval. Every step is traceable.

---

## PART 7 — Wrap-Up (4:50 – 5:00)

**[Screen: Go back to dashboard. Point mouse at the metrics strip — total cases, auto-approved count, STP rate.]**

Back on the dashboard — you can see the straight-through processing rate, total approved amount, and cases needing attention. Everything is auditable, deterministic, and fully traceable.

That's InvoicePilot. Thank you.

---

## CHEAT SHEET — File Upload Order

| # | File to Upload | Expected Result |
|---|---------------|----------------|
| 1 | `happy_path_apex_invoice.pdf` | AUTO_APPROVED |
| 2 | `duplicate_original_meridian.pdf` | AUTO_APPROVED |
| 3 | `duplicate_reissued_meridian.pdf` | BLOCKED |
| 4 | `cumulative_a_meridian.pdf` | AUTO_APPROVED (tolerance warning) |
| 5 | `cumulative_b_meridian.pdf` | NEEDS_REVIEW |
| 6 | `ambiguous_po_brightwave.pdf` | NEEDS_REVIEW → AUTO_APPROVED after PO select |
| 7 | `scanned_missing_number_pinnacle.pdf` | NEEDS_INFORMATION |
| 8 | `scanned_corrected_pinnacle.pdf` (as revision of #7) | AUTO_APPROVED |

### Before Recording Checklist:
- [ ] Hit "Demo Reset" on dashboard
- [ ] Check `/health-page` — make sure Tesseract shows OK (needed for scenarios 7-8)
- [ ] Pre-download all 8 fixture PDFs so you don't fumble during recording
- [ ] Keep this file open on a second monitor or to the side as your teleprompter
