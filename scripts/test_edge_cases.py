"""Test all four edge-case families against the running server."""
import httpx
import sys

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  ✓ {name}")
        PASS += 1
    else:
        print(f"  ✗ {name}: {detail}")
        FAIL += 1

def upload(filename):
    with open(f"data/fixtures/{filename}", "rb") as f:
        resp = httpx.post(f"{BASE}/api/upload", files={"file": (filename, f, "application/pdf")}, timeout=30)
    return resp.json()

def reset():
    httpx.post(f"{BASE}/api/demo/reset", timeout=30)

def get_case(case_id):
    resp = httpx.get(f"{BASE}/api/cases/{case_id}", timeout=10)
    return resp.json()

# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("InvoicePilot Edge Case Tests")
print("=" * 60)

# ── Reset to baseline ──
print("\n→ Resetting to demo baseline...")
reset()
print("  Done.\n")

# ═══════════════════════════════════════════════════════════════
# HAPPY PATH
# ═══════════════════════════════════════════════════════════════
print("─── Happy Path ─────────────────────────────────")
r = upload("happy_path_apex_invoice.pdf")
check("Decision is AUTO_APPROVED", r.get("decision") == "AUTO_APPROVED", r.get("decision"))
check("Reason is ALL_CHECKS_PASSED", r.get("primary_reason_code") == "ALL_CHECKS_PASSED", r.get("primary_reason_code"))

if r.get("case_id") and not r.get("is_byte_duplicate"):
    detail = get_case(r["case_id"])
    check("Net is $2,500.00 (250000 cents)", detail["case"]["net_cents"] == 250000, detail["case"]["net_cents"])
    check("Gross is $2,700.00 (270000 cents)", detail["case"]["gross_cents"] == 270000, detail["case"]["gross_cents"])
    check("PO is PO-1001", detail["case"]["po_id"] == "PO-1001", detail["case"]["po_id"])
    check("Has commitment", len(detail["commitments"]) > 0)
    if detail["commitments"]:
        check("Commitment is $2,500.00", detail["commitments"][0]["net_amount_cents"] == 250000,
              detail["commitments"][0]["net_amount_cents"])

# ═══════════════════════════════════════════════════════════════
# EDGE FAMILY 1: Duplicates
# ═══════════════════════════════════════════════════════════════
print("\n─── Edge Family 1: Duplicates ──────────────────")

# First, upload the "original" that will be the approved duplicate target
print("  Uploading duplicate original (Meridian MCG-2026-0088)...")
r_orig = upload("duplicate_original_meridian.pdf")
check("Original approved", r_orig.get("decision") == "AUTO_APPROVED", r_orig.get("decision"))
orig_case_id = r_orig.get("case_id")

# Test 1a: Identical bytes (upload same file again)
print("\n  Test 1a: Identical bytes...")
r_bytes = upload("duplicate_original_meridian.pdf")
check("Byte duplicate detected", r_bytes.get("is_byte_duplicate") == True, r_bytes.get("is_byte_duplicate"))

# Test 1b: Different PDF, same business identity + same amounts
print("\n  Test 1b: Reissued duplicate (different bytes, same data)...")
r_reissued = upload("duplicate_reissued_meridian.pdf")
check("Decision is BLOCKED", r_reissued.get("decision") == "BLOCKED", r_reissued.get("decision"))
check("Reason is DUPLICATE_INVOICE", r_reissued.get("primary_reason_code") == "DUPLICATE_INVOICE",
      r_reissued.get("primary_reason_code"))

# Test 1c: Same vendor/invoice# but different amounts
print("\n  Test 1c: Identity collision (different amounts)...")
r_collision = upload("duplicate_collision_meridian.pdf")
check("Decision is NEEDS_REVIEW", r_collision.get("decision") == "NEEDS_REVIEW", r_collision.get("decision"))
check("Reason is INVOICE_IDENTITY_COLLISION",
      r_collision.get("primary_reason_code") == "INVOICE_IDENTITY_COLLISION",
      r_collision.get("primary_reason_code"))

# ═══════════════════════════════════════════════════════════════
# EDGE FAMILY 2: Cumulative Tolerance
# ═══════════════════════════════════════════════════════════════
print("\n─── Edge Family 2: Cumulative Budget ───────────")
# PO-1002: $10,000 PO net, $6,000 already committed (seed)
# Overage = min(10000*0.01, 50) = $50. Ceiling = $10,050
reset()  # Fresh start for cumulative tests

# Test 2a: Invoice A - $4,040 net → projected $10,040 ≤ $10,050
print("  Test 2a: Cumulative A ($4,040 net, projected $10,040)...")
r_a = upload("cumulative_a_meridian.pdf")
check("Decision is AUTO_APPROVED", r_a.get("decision") == "AUTO_APPROVED", r_a.get("decision"))

# Test 2b: Reset and test B - $4,060 net → projected $10,060 > $10,050
print("\n  Resetting for isolated Test 2b...")
reset()
# Re-upload happy path to keep it but we just need PO-1002 seed
print("  Test 2b: Cumulative B ($4,060 net, projected $10,060)...")
r_b = upload("cumulative_b_meridian.pdf")
check("Decision is NEEDS_REVIEW", r_b.get("decision") == "NEEDS_REVIEW", r_b.get("decision"))
check("Reason is PO_CUMULATIVE_LIMIT_EXCEEDED",
      r_b.get("primary_reason_code") == "PO_CUMULATIVE_LIMIT_EXCEEDED",
      r_b.get("primary_reason_code"))

# Test 2c: Sequential A then C - after A approved ($10,040), C adds $20 → $10,060
print("\n  Resetting for sequential Test 2c...")
reset()
print("  Approving A first...")
r_a2 = upload("cumulative_a_meridian.pdf")
check("A approved", r_a2.get("decision") == "AUTO_APPROVED", r_a2.get("decision"))
print("  Then uploading C ($20 net)...")
r_c = upload("cumulative_c_meridian.pdf")
check("Decision is NEEDS_REVIEW", r_c.get("decision") == "NEEDS_REVIEW", r_c.get("decision"))
check("Reason includes cumulative limit",
      r_c.get("primary_reason_code") == "PO_CUMULATIVE_LIMIT_EXCEEDED",
      r_c.get("primary_reason_code"))

# ═══════════════════════════════════════════════════════════════
# EDGE FAMILY 3: Ambiguous PO
# ═══════════════════════════════════════════════════════════════
print("\n─── Edge Family 3: Ambiguous PO ────────────────")
reset()
r_ambig = upload("ambiguous_po_brightwave.pdf")
check("Decision is NEEDS_REVIEW", r_ambig.get("decision") == "NEEDS_REVIEW", r_ambig.get("decision"))
check("Reason is PO_AMBIGUOUS", r_ambig.get("primary_reason_code") == "PO_AMBIGUOUS",
      r_ambig.get("primary_reason_code"))
check("Has PO candidates", len(r_ambig.get("po_candidates", [])) >= 2,
      f"candidates: {len(r_ambig.get('po_candidates', []))}")

# Test reviewer PO selection
if r_ambig.get("case_id"):
    print("\n  Testing reviewer PO selection...")
    form_data = {"po_id": "PO-1005", "reason": "Service matches pipeline development scope"}
    resp = httpx.post(f"{BASE}/api/cases/{r_ambig['case_id']}/review/select-po",
                      data=form_data, timeout=30)
    r_review = resp.json()
    check("Re-evaluation completed", r_review.get("decision") is not None, r_review)
    check("After PO selection, auto-approved",
          r_review.get("decision") == "AUTO_APPROVED", r_review.get("decision"))

# ═══════════════════════════════════════════════════════════════
# EDGE FAMILY 4: Scanned / Missing Invoice Number
# ═══════════════════════════════════════════════════════════════
print("\n─── Edge Family 4: Scanned / Missing Number ────")
reset()
r_scan = upload("scanned_missing_number_pinnacle.pdf")
check("Decision is NEEDS_INFORMATION", r_scan.get("decision") == "NEEDS_INFORMATION", r_scan.get("decision"))
check("Reason involves missing invoice number",
      "MISSING" in (r_scan.get("primary_reason_code") or ""),
      r_scan.get("primary_reason_code"))

# Test corrected revision upload
if r_scan.get("case_id"):
    print("\n  Testing corrected revision upload...")
    with open("data/fixtures/scanned_corrected_pinnacle.pdf", "rb") as f:
        resp = httpx.post(
            f"{BASE}/api/cases/{r_scan['case_id']}/review/attach-revision",
            files={"file": ("scanned_corrected_pinnacle.pdf", f, "application/pdf")},
            data={"reason": "Vendor provided corrected invoice with invoice number"},
            timeout=30,
        )
    r_corrected = resp.json()
    check("Corrected version processed", r_corrected.get("decision") is not None, r_corrected)
    check("After correction, auto-approved or reviewed",
          r_corrected.get("decision") in ("AUTO_APPROVED", "NEEDS_REVIEW"), r_corrected.get("decision"))

# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"Results: {PASS} passed, {FAIL} failed")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
