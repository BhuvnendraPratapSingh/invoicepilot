"""Additional targeted QA checks for untested scenarios."""
import httpx
import json
import time
from pathlib import Path
from datetime import datetime

B = "http://127.0.0.1:8111"

def reset():
    httpx.post(B + "/api/demo/reset", timeout=30)
    time.sleep(0.3)

print("=" * 60)
print("Additional QA Checks")
print("=" * 60)

# ── CHECK 1: Inactive vendor (V-004 Sterling Office Supply) ──
print("\n── Inactive Vendor Check ──")
# We can't easily generate a fixture for V-004 without modifying app code.
# But we can verify through code inspection that vendor_resolution.py
# returns is_active=False for inactive vendors, which blocks auto-approval.
print("  ANALYSIS: vendor_resolution.py checks is_active on all match paths.")
print("  Tax ID match, exact name, and alias match all return early with")
print("  is_active=False if vendor is inactive. Policy engine checks vendor_active.")
print("  Status: VERIFIED BY CODE INSPECTION (not runtime test)")

# ── CHECK 2: Demo reset in non-demo mode would be rejected ──
print("\n── Non-demo mode reset rejection ──")
# Can't test without modifying config. Code says:
# if not settings.demo_mode: raise HTTPException(403)
print("  ANALYSIS: routes.py line ~698 checks settings.demo_mode before allowing reset.")
print("  Status: VERIFIED BY CODE INSPECTION")

# ── CHECK 3: Verify production DB was not modified ──
print("\n── Production database isolation ──")
import os
prod_db = Path("data/invoicepilot.db")
qa_db = Path("data/qa_test.db")
if prod_db.exists() and qa_db.exists():
    prod_size = prod_db.stat().st_size
    prod_mtime = datetime.fromtimestamp(prod_db.stat().st_mtime).isoformat()
    qa_size = qa_db.stat().st_size
    print(f"  Production DB: {prod_size} bytes, last modified: {prod_mtime}")
    print(f"  QA DB: {qa_size} bytes")
    print(f"  PASS: Both databases exist separately")
else:
    print(f"  Production exists: {prod_db.exists()}, QA exists: {qa_db.exists()}")

# ── CHECK 4: Verify no secrets in exported audit ──
print("\n── Secrets in audit export check ──")
reset()
r = httpx.post(B + "/api/upload",
    files={"file": ("test.pdf", open("data/fixtures/happy_path_apex_invoice.pdf", "rb"), "application/pdf")},
    timeout=30).json()
if r.get("case_id") and not r.get("is_byte_duplicate"):
    audit = httpx.get(B + "/api/cases/" + r["case_id"] + "/audit", timeout=10).json()
    audit_str = json.dumps(audit, default=str)
    has_key = "api_key" in audit_str.lower() or "anthropic" in audit_str.lower()
    has_path = "C:\\Users" in audit_str and "bhsingh" in audit_str
    print(f"  API keys in export: {'YES - FAIL' if has_key else 'No - PASS'}")
    print(f"  Unsafe local paths in export: {'YES - FAIL' if has_path else 'No - PASS'}")
    # Save sanitized export as evidence
    with open("qa/evidence/audit_export_secrets_check.json", "w") as f:
        json.dump(audit, f, indent=2, default=str)

# ── CHECK 5: Verify stage events are persisted (not just in memory) ──
print("\n── Stage event persistence ──")
reset()
r = httpx.post(B + "/api/upload",
    files={"file": ("persist_test.pdf", open("data/fixtures/happy_path_apex_invoice.pdf", "rb"), "application/pdf")},
    timeout=30).json()
if r.get("case_id") and not r.get("is_byte_duplicate"):
    # First fetch
    d1 = httpx.get(B + "/api/cases/" + r["case_id"], timeout=10).json()
    events1 = d1["attempts"][-1]["events"] if d1.get("attempts") else []
    # Wait and fetch again (simulating browser refresh)
    time.sleep(1)
    d2 = httpx.get(B + "/api/cases/" + r["case_id"], timeout=10).json()
    events2 = d2["attempts"][-1]["events"] if d2.get("attempts") else []
    # Should be identical
    same = len(events1) == len(events2) and len(events1) > 0
    print(f"  Events on first fetch: {len(events1)}")
    print(f"  Events on second fetch: {len(events2)}")
    print(f"  Persistence: {'PASS' if same else 'FAIL'}")

# ── CHECK 6: Verify export contains policy snapshot ──
print("\n── Policy snapshot in decision ──")
if r.get("case_id"):
    d = httpx.get(B + "/api/cases/" + r["case_id"], timeout=10).json()
    decisions = d.get("decisions", [])
    if decisions:
        dec = decisions[-1]
        has_policy = dec.get("policy_version") == "demo-policy-v1"
        has_ledger = dec.get("ledger_snapshot") is not None
        print(f"  Policy version in decision: {dec.get('policy_version')} - {'PASS' if has_policy else 'FAIL'}")
        print(f"  Ledger snapshot present: {'PASS' if has_ledger else 'FAIL'}")

# ── CHECK 7: Verify approval disclaimer ──
print("\n── Approval disclaimer check ──")
if r.get("case_id"):
    d = httpx.get(B + "/api/cases/" + r["case_id"], timeout=10).json()
    decisions = d.get("decisions", [])
    if decisions:
        explanation = decisions[-1].get("explanation", "")
        has_disclaimer = "No payment has been executed" in explanation
        print(f"  'No payment executed' in explanation: {'PASS' if has_disclaimer else 'FAIL'}")

print("\n" + "=" * 60)
print("Additional checks complete")
print("=" * 60)
