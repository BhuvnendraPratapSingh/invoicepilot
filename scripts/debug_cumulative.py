"""Debug cumulative A extraction."""
import httpx

BASE = "http://127.0.0.1:8000"
httpx.post(f"{BASE}/api/demo/reset", timeout=30)

with open("data/fixtures/cumulative_a_meridian.pdf", "rb") as f:
    r = httpx.post(f"{BASE}/api/upload", files={"file": ("cumulative_a_meridian.pdf", f, "application/pdf")}, timeout=30)

d = r.json()
print(f"Decision: {d.get('decision')}")
print(f"Reason: {d.get('primary_reason_code')}")
print(f"Explanation: {d.get('explanation')}")

if d.get("case_id") and not d.get("is_byte_duplicate"):
    detail = httpx.get(f"{BASE}/api/cases/{d['case_id']}", timeout=10).json()
    att = detail["attempts"][-1]
    ext = att.get("extracted_data") or {}
    print(f"\nExtracted: net={ext.get('net_total_cents')}, gross={ext.get('gross_total_cents')}, sub={ext.get('subtotal_cents')}, tax={ext.get('tax_cents')}")
    print(f"Invoice#: {ext.get('invoice_number')}, PO: {ext.get('po_reference')}, Vendor: {ext.get('vendor_name')}")
    print(f"\nRule results:")
    for rule in att.get("rules", []):
        marker = "✓" if rule["result"] == "PASS" else "✗"
        print(f"  {marker} {rule['rule_name']}: {rule['explanation'][:120]}")

    # Budget info
    if detail.get("budget"):
        b = detail["budget"]
        print(f"\nBudget: PO net={b['po_net_display']}, committed={b['committed_display']}, ceiling={b['ceiling_display']}")
