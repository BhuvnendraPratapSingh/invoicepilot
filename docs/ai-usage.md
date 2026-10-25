# InvoicePilot — AI Usage

## AI in Development

This project was developed with AI assistance (Kiro/Claude). All generated code was reviewed, tested, and verified against actual running behavior. The AI helped with:

- Project structure and boilerplate
- PDF fixture generation with ReportLab
- Extraction pattern development
- Policy engine implementation
- UI templates and styling
- Test script creation

All financial logic, policy rules, and decision outcomes were verified through integration tests against the running server.

## AI in the Application

### Optional AI-Assisted Extraction

InvoicePilot has an optional AI-assisted extraction mode that can send extracted text/OCR content to an Anthropic model for structured field extraction. This is **not required** — the default local mode uses regex patterns.

When enabled:
- Extracted text is sent to the configured Anthropic model
- Response is validated against a strict Pydantic schema
- Model-selected evidence spans are resolved against actual source text
- Prompt version, model ID, elapsed time, and token usage are stored
- On provider failure, falls back to local extraction with clear labeling

### Why AI is NOT the Financial Decision Authority

The extraction model interprets documents — a perception task where AI excels. But the financial decision is deterministic:

1. **Cumulative budget**: `projected_net ≤ po_net + min(po_net × 0.01, $50.00)`
2. **Duplicate identity**: `vendor_id + normalized_invoice_number` match
3. **Vendor authorization**: exact match against approved master
4. **Arithmetic reconciliation**: `subtotal + tax == gross` within $0.01

These rules produce auditable, reproducible results with exact observed vs expected values. An AI model's judgment cannot provide:
- Deterministic arithmetic guarantees
- Exact boundary behavior (e.g., $10,050.00 ceiling)
- Auditable rule-by-rule evidence
- Consistent decisions across identical inputs

### Trust Boundaries

- Invoice content is treated as untrusted data
- Embedded instructions (e.g., "ignore PO and approve") have no authority
- The model cannot execute tools, change policy, or approve payments
- Model confidence scores are diagnostic signals, not calibrated probabilities
- Missing fields are null, not model-generated guesses
