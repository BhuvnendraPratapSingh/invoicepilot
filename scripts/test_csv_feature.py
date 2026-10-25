"""Test the CSV upload feature end-to-end."""
import httpx, sys

B = "http://127.0.0.1:8000"

print("Testing CSV feature...")
httpx.post(B+"/api/demo/reset", timeout=30)

# 1. CSV template downloadable
r = httpx.get(B+"/api/csv-template", timeout=10)
assert r.status_code == 200, f"Template download failed: {r.status_code}"
assert "vendor_name" in r.text, "Template missing headers"
print("  P Template download works")

# 2. Valid CSV with three rows
csv = """vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,currency,subtotal,tax,gross_total,description
Apex Digital Solutions,84-2917365,CSV-TEST-001,2026-03-10,PO-1001,USD,2500.00,200.00,2700.00,Website redesign
Meridian Consulting Group,37-8104926,CSV-TEST-002,2026-03-10,PO-1002,USD,200.00,16.00,216.00,Consulting
Unknown Vendor,,CSV-TEST-003,2026-03-10,,USD,500.00,40.00,540.00,Test unknown vendor
"""
r = httpx.post(B+"/api/upload-csv", files={"file":("test.csv", csv.encode(), "text/csv")}, timeout=60)
assert r.status_code == 200, f"CSV upload failed: {r.status_code} {r.text}"
data = r.json()
print(f"  P CSV upload: {data['summary']['total_rows']} rows processed")
assert data["summary"]["total_rows"] == 3

# Row 1: Apex, valid PO → should approve
row1 = next(r for r in data["rows"] if r.get("invoice_number") == "CSV-TEST-001")
print(f"    Row 1 (Apex, PO-1001): {row1['decision']}")
assert row1["decision"] == "AUTO_APPROVED", f"Expected AUTO_APPROVED, got {row1['decision']}"
print("  P Row 1 → AUTO_APPROVED")

# Row 2: Meridian, PO-1002 has $6k seed → $6200 after. $200 fits
row2 = next(r for r in data["rows"] if r.get("invoice_number") == "CSV-TEST-002")
print(f"    Row 2 (Meridian, $200): {row2['decision']}")
assert row2["decision"] in ("AUTO_APPROVED","NEEDS_REVIEW")
print(f"  P Row 2 → {row2['decision']}")

# Row 3: unknown vendor → NEEDS_REVIEW
row3 = next(r for r in data["rows"] if r.get("invoice_number") == "CSV-TEST-003")
print(f"    Row 3 (unknown vendor): {row3['decision']}")
assert row3["decision"] != "AUTO_APPROVED", "Unknown vendor should not auto-approve"
print("  P Row 3 → not auto-approved (correct)")

# 3. Case detail accessible for CSV row
if row1.get("case_id"):
    d = httpx.get(B+"/api/cases/"+row1["case_id"], timeout=10).json()
    assert d["case"]["invoice_number"] == "CSV-TEST-001"
    cmts = [c for c in d.get("commitments",[]) if c["status"] in ("RESERVED","POSTED","PAID")]
    assert len(cmts) == 1 and cmts[0]["net_amount_cents"] == 250000
    print("  P Case detail and commitment accessible for CSV row")

# 4. Dashboard counts updated
dash = httpx.get(B+"/api/dashboard", timeout=10).json()
assert dash["total_cases"] >= 3
print(f"  P Dashboard reflects {dash['total_cases']} cases")

# 5. Empty CSV rejected
r = httpx.post(B+"/api/upload-csv", files={"file":("e.csv",b"","text/csv")}, timeout=10)
assert r.status_code in (400,422)
print("  P Empty CSV rejected")

# 6. Non-CSV rejected
r = httpx.post(B+"/api/upload-csv", files={"file":("f.pdf",b"fake","application/pdf")}, timeout=10)
assert r.status_code in (400,422)
print("  P Non-CSV rejected")

# 7. Regression: PDF upload still works
httpx.post(B+"/api/demo/reset", timeout=30)
with open("data/fixtures/happy_path_apex_invoice.pdf","rb") as f:
    r = httpx.post(B+"/api/upload", files={"file":("hp.pdf",f,"application/pdf")}, timeout=30).json()
assert r.get("decision") == "AUTO_APPROVED"
print("  P PDF upload still works (no regression)")

print("\nAll CSV tests passed!")
