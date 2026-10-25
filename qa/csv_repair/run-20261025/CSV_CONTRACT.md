# CSV Import Contract — InvoicePilot

## Type: Invoice Import (Branch A)
Each CSV row represents one complete invoice. One row → one case → one decision.

## Endpoint
`POST /api/upload-csv`
Field: `file` (multipart, `.csv` only)
Size limit: 2 MB
Response: `{"summary": {...}, "rows": [...]}`

## Headers (case-insensitive, whitespace-stripped)

| Column | Required | Aliases | Notes |
|---|---|---|---|
| `vendor_name` | One of these two | — | Matched against vendor master |
| `vendor_tax_id` | One of these two | — | EIN; preferred over name if present |
| `invoice_number` | ✅ | — | Preserved exactly; leading zeros safe |
| `invoice_date` | ✅ | — | YYYY-MM-DD or "March 10, 2026" |
| `po_reference` | Optional | — | e.g. PO-1001; absence routes to PO_AMBIGUOUS |
| `currency` | Optional | — | Defaults to USD; non-USD → NEEDS_REVIEW |
| `subtotal` | One of these two | `net_amount` | Net amount before tax |
| `gross_total` | One of these two | `total`, `amount_due` | Total due |
| `tax` | Optional | `tax_amount` | If absent, net derived from gross (requires subtotal absent) |
| `description` | Optional | — | Service description |

Extra columns are silently ignored. Duplicate headers: last-write-wins (documented limitation).

## Encoding
- UTF-8 (with or without BOM) is the primary format
- Latin-1 fallback attempted on UTF-8 decode failure
- Unsupported encodings return 400

## Monetary Values
- Parsed via `Decimal`; never float arithmetic
- Accepted: `2500.00`, `2,500`, `$2,500.00`, `2500`
- Rejected: `abc`, empty, `NaN`, `inf`
- Sub-cent values: truncated to cents via `int(Decimal * 100)`

## Dates
- Demo business clock: 2026-03-15
- Future dates → NEEDS_REVIEW

## Atomicity
Each row is processed independently. A failed row does not roll back earlier rows.
The response includes per-row decisions.

## Financial Rules Applied (same as PDF)
- Vendor must exist and be active in approved master
- PO must exist, be OPEN/APPROVED, belong to the invoice vendor, and have capacity
- Arithmetic: subtotal + tax must equal gross_total within $0.01
- Cumulative PO overage: min(1% of original PO net, $50.00)
- All duplicate checks apply (byte-duplicate = N/A for CSV; business duplicate applies)

## Supported Limitations
- No multi-PO allocation per row
- No credit notes or non-USD (NEEDS_REVIEW)
- No line-item grouping; one row = one invoice (bundled)
- No CSV export of results
