"""Quick API smoke test."""
import httpx

BASE = "http://127.0.0.1:8000"

# Health
resp = httpx.get(f"{BASE}/api/health")
print("Health:", resp.json()["status"])

# Dashboard
resp = httpx.get(f"{BASE}/api/dashboard")
d = resp.json()
print(f"Dashboard: {d['total_cases']} cases, demo={d['demo_mode']}")

# Fixtures
resp = httpx.get(f"{BASE}/api/fixtures")
print(f"Fixtures: {len(resp.json())} available")

# Upload happy path
with open("data/fixtures/happy_path_apex_invoice.pdf", "rb") as f:
    resp = httpx.post(f"{BASE}/api/upload", files={"file": ("happy_path_apex_invoice.pdf", f, "application/pdf")}, timeout=30)
result = resp.json()
print(f"\nUpload result: decision={result.get('decision')}, reason={result.get('primary_reason_code')}")
print(f"  Case ID: {result.get('case_id')}")
print(f"  Explanation: {result.get('explanation')}")
print(f"  Is byte dup: {result.get('is_byte_duplicate')}")

# Get case detail
if result.get("case_id") and not result.get("is_byte_duplicate"):
    resp = httpx.get(f"{BASE}/api/cases/{result['case_id']}")
    detail = resp.json()
    c = detail["case"]
    print(f"  Vendor: {c.get('vendor_name')}, Invoice#: {c.get('invoice_number')}")
    print(f"  Gross: {c.get('gross_cents')} cents, Net: {c.get('net_cents')} cents")
    if detail.get("commitments"):
        for cmt in detail["commitments"]:
            print(f"  Commitment: {cmt['net_display']} on {cmt['po_id']} ({cmt['status']})")
    if detail.get("attempts"):
        att = detail["attempts"][-1]
        print(f"  Events: {len(att['events'])} stages")
        for ev in att["events"]:
            msg = ev.get('message') or ''
            print(f"    {ev['stage_name']}: {ev['status']} - {msg[:80]}")
        if att.get("rules"):
            print(f"\n  Rules ({len(att['rules'])}):")
            for r in att["rules"]:
                print(f"    {r['result']:4s} {r['rule_name']}: {r.get('explanation','')[:80]}")
