# InvoicePilot — Interview Notes

Short, code-grounded answers to anticipated questions.

## Why is AI used for extraction but not trusted to approve?

Extraction is a perception task — interpreting messy document layouts, varied labels, OCR noise. AI is good at that. But approval is a financial control with specific numeric rules: cumulative budgets, duplicate identity, vendor authorization. These rules are deterministic and auditable. If we let a model decide approvals, we can't explain exactly why a $10,060 commitment was allowed against a $10,050 ceiling. The policy engine in `app/services/policy_engine.py` produces rule-by-rule results with observed vs expected values. A model's "I think this should be approved" isn't auditable the same way.

## Why does missing or ambiguous evidence lead to review/information requests?

Because the cost of a false approval is much higher than the cost of a review delay. If we can't confirm the invoice number, we can't detect duplicates. If we can't confirm the vendor, we can't check authorization. The policy engine in `evaluate_policy()` separates NEEDS_INFORMATION (can't evaluate because facts are missing) from NEEDS_REVIEW (evaluated but found ambiguity). Both are actionable — they tell the reviewer exactly what's needed and why.

## Why are tax and net/gross comparisons tricky?

PO capacity is a net concept — it covers the cost of services, not the tax. Comparing invoice gross ($2,700) against PO net ($2,500) would incorrectly flag a $200 overage that's just tax. Our pipeline derives `invoice_net = subtotal - discount + shipping`, then compares net-to-net. For tax-inclusive documents, we derive net = gross - tax and label it as derived. Ambiguous tax treatment routes to NEEDS_INFORMATION rather than guessing. See the budget check in `policy_engine.py` rule `PO_BUDGET`.

## How does split invoicing change tolerance logic?

The tolerance (`min(PO_net × 1%, $50)`) applies once to the entire PO, not per invoice. In `_calculate_overage()`, we compute the ceiling from the original PO amount, then check `sum(all_active_commitments) + current_invoice_net <= ceiling`. Edge case 2c proves this: after approving invoice A ($4,040 net, cumulative $10,040), a $20 follow-up brings cumulative to $10,060. That's $10 over the $10,050 ceiling even though $20 seems trivial. The small invoice doesn't get a fresh tolerance.

## How are duplicate detection and idempotency different?

Idempotency (byte-level, `duplicate_detection.py:check_byte_duplicate`) answers: "Have I seen these exact bytes before?" It's a SHA-256 match. Same file uploaded twice → link to existing case, no new processing. Business duplicates answer: "Is this the same invoice from this vendor?" That's vendor_id + normalized_invoice_number. Same identity + same amounts + active approval → BLOCKED. Same identity + different amounts → IDENTITY_COLLISION for review. These are distinct situations with different responses.

## What prevents two concurrent runs from consuming the same capacity?

In `orchestrator.py`, the decision and reservation are committed in a single SQLAlchemy/SQLite transaction. Before writing the commitment, we re-check PO exposure inside the transaction using `_get_committed_cents()`. SQLite's WAL mode with busy timeout and FK constraints prevent two transactions from both reserving the same capacity. The `UniqueConstraint("case_id", "po_id")` on commitments prevents double reservations for the same case. This is a demo-level guarantee; production would use a database with proper row-level locking.

## What exactly is persisted when a reviewer changes something?

A `ReviewAction` record captures: actor, action type, before/after values, reason, and timestamp. The system creates a new `ProcessingAttempt` with trigger="review", runs all stages against current database state (not cached results), and produces new `ExtractedData`, `RuleResult`, and `Decision` records. The original attempt and its evidence remain intact — we don't mutate history. If the selected PO no longer has capacity, the re-evaluation fails the budget check instead of overriding it.

## Which parts work offline and which genuinely use an external model?

Everything works offline by default. The local extraction in `extraction.py` uses regex patterns against document text. OCR uses local Tesseract. The optional AI-assisted mode (`ai_extraction_enabled=true`) sends extracted text to Anthropic's API for structured field extraction, but it's not required. The model's output is validated against the same Pydantic schema and cross-referenced against actual source text. The model cannot approve, reject, or change policy.

## What is two-way matching missing compared with three-way matching?

Two-way: invoice matches PO. We confirm the vendor is authorized, the PO exists and has capacity, and amounts reconcile. Three-way adds: receipt of goods/services. Did we actually receive what the vendor invoiced? Without receipt verification, we could approve an invoice for services never delivered. This is explicitly labeled as out of scope in the decision and documentation. Production AP systems verify receipt before authorizing payment.

## What did you deliberately not build, and why?

- **Payment execution**: this is a decision workbench, not a treasury system
- **Authentication**: demo scope; adding JWT/SSO wouldn't prove AP logic understanding
- **Multi-currency**: FX adds complexity without demonstrating core matching concepts
- **Credit notes**: different workflow (negative amounts, reversals)
- **Three-way matching**: requires a goods-receipt system we don't have
- **Complex policy UI**: a config file proves the policy is configurable without building a form
- **Microservices**: one process with bounded workers is appropriate for demo scale

## What is verified, what is only a demo assumption, and what would need production hardening?

**Verified**: All four edge cases run through the real pipeline. Extraction reads actual PDF text. Budget arithmetic uses Decimal. Duplicate detection uses actual SHA-256 and normalized identity. Tests run against the live server.

**Demo assumptions**: Single process, single user, no auth, Tesseract installed, deterministic business date, small fixture family.

**Production hardening needed**: Authentication/authorization, durable job queue (not in-process executor), database migration management, row-level locking (PostgreSQL), receipt verification, extraction evaluation across many layouts, content security sandboxing, monitoring/alerting, backup/recovery.
