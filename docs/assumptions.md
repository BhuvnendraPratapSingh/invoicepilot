# InvoicePilot — Assumptions

## Scope Assumptions

### Invoice Types
- **Service invoices only** — no goods receipts, no three-way matching
- Two-way match: invoice ↔ purchase order. Receipt of goods/services is NOT verified.
- USD only. Non-USD invoices route to NEEDS_REVIEW with reason UNSUPPORTED_CURRENCY.
- Credit notes and negative totals route to NEEDS_REVIEW with reason UNSUPPORTED_DOCUMENT_TYPE.
- Multi-PO invoices route to NEEDS_REVIEW with reason MULTI_PO_NOT_SUPPORTED.

### Vendor Master
- Loaded from validated CSV into SQLite on startup/reset
- Vendors have: ID, name, tax_id, aliases, status (active/inactive)
- A vendor must be active and in the approved master to auto-approve
- Fuzzy name matching suggests candidates but cannot establish approval

### Purchase Orders
- Loaded from validated CSV into SQLite
- POs have: number, vendor_id, description, service_scope, net_amount, currency, status
- Only OPEN/APPROVED POs are eligible for matching
- PO capacity = original_net + allowed_overage - sum(active_commitments)

### Financial Rules (demo-policy-v1)
- Currency: USD only
- Arithmetic tolerance: $0.01
- PO overage tolerance: min(original_po_net × 0.01, $50.00), rounded to cents (half-up)
- Tolerance is cumulative — applies once to total PO commitment, not per invoice
- All money uses Decimal (two decimal places) — never floating point
- invoice_net = subtotal − discount + shipping (when components clearly evidenced)
- invoice_gross = invoice_net + tax (for tax-exclusive documents)
- PO capacity compared to invoice NET, never gross

### Tax Treatment
- We validate arithmetic, not jurisdiction-specific tax legality
- Tax-exclusive: net is stated, gross = net + tax
- Tax-inclusive with explicit tax: derive net = gross − tax, preserve derivation
- Ambiguous tax treatment → NEEDS_INFORMATION

### Dates
- Configurable business date for reproducible demo (labeled as demo clock)
- Real execution timestamps kept separate
- Future invoice dates → NEEDS_REVIEW
- Old invoices are not rejected merely for age (optional warning only)

## What "Auto-Approved" Means
- All demo AP policy checks passed
- PO capacity reserved (net amount only)
- **NOT**: payment authorized, delivery confirmed, legally binding, or ERP-posted
- The UI always shows: "No payment has been executed"

## What This System Does NOT Do
- Execute payments or bank transfers
- Post to an ERP or general ledger
- Send real emails or connect to mailboxes
- Authenticate users (demo actor labels only)
- Handle multi-tenancy or SSO
- Verify goods/services receipt (three-way match)
- Validate tax jurisdiction compliance
- Process FX conversions
- Handle credit notes or negative amounts
- Allocate one invoice across multiple POs

## Duplicate Handling
- **Byte-level**: SHA-256 match → link to existing case, no new processing
- **Business identity**: vendor_id + normalized_invoice_number
  - Same identity + same amounts + active approval → BLOCKED
  - Same identity + different amounts → NEEDS_REVIEW (collision)
  - Similar amount/date/vendor without reliable ID → suspected duplicate warning
- An unresolved earlier submission is not proof of duplicate payable

## Security Model
- Local-only binding, no public CORS
- No authentication (demo limitation, clearly documented)
- HTML escaping on all user/document text
- Generated storage filenames, path traversal prevention
- No secrets in browser, logs, or exports
- PDF content treated as untrusted data
- Embedded instructions in invoices have no authority
- Hostile document sandboxing is out of demo scope (documented)

## Audit Model
- Append-only by application behavior (not cryptographically enforced)
- A database administrator could modify records (honest limitation)
- Every decision stores: policy version, data snapshots, evidence, rule results
- Exports allow inspection without opening the app
