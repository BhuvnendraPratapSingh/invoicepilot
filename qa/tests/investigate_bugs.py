"""Investigate specific QA failures."""
import httpx

B = "http://127.0.0.1:8111"

print("=== BUG INVESTIGATION: Byte-dup orphan case ===")
httpx.post(B + "/api/demo/reset", timeout=30)

r1 = httpx.post(B + "/api/upload",
    files={"file": ("f1.pdf", open("data/fixtures/happy_path_apex_invoice.pdf", "rb"), "application/pdf")},
    timeout=30).json()
print("Upload 1:", r1.get("case_id", "")[:12], "decision=" + str(r1.get("decision")))

r2 = httpx.post(B + "/api/upload",
    files={"file": ("f1.pdf", open("data/fixtures/happy_path_apex_invoice.pdf", "rb"), "application/pdf")},
    timeout=30).json()
print("Upload 2:", r2.get("case_id", "")[:12], "byte_dup=" + str(r2.get("is_byte_duplicate")))

cases = httpx.get(B + "/api/cases", timeout=10).json()
non_seed = [c for c in cases if not c["id"].startswith("SEED-")]
print("Non-seed case count:", len(non_seed))
for c in non_seed:
    print("  " + c["id"][:12] + "... decision=" + str(c["decision"]) + " inv=" + str(c["invoice_number"]))

print()
print("=== BUG INVESTIGATION: CUM-05 exact ceiling fixture ===")
httpx.post(B + "/api/demo/reset", timeout=30)
r = httpx.post(B + "/api/upload",
    files={"file": ("cumulative_exact_ceiling.pdf",
           open("qa/fixtures/cumulative_exact_ceiling.pdf", "rb"), "application/pdf")},
    timeout=30).json()
print("CUM-05 result:", r.get("decision"), r.get("primary_reason_code"))
print("Explanation:", r.get("explanation"))
if r.get("case_id") and not r.get("is_byte_duplicate"):
    d = httpx.get(B + "/api/cases/" + r["case_id"], timeout=10).json()
    if d.get("attempts"):
        ext = d["attempts"][-1].get("extracted_data") or {}
        print("Extracted net:", ext.get("net_total_cents"), "gross:", ext.get("gross_total_cents"),
              "sub:", ext.get("subtotal_cents"), "tax:", ext.get("tax_cents"))
        print("Invoice#:", ext.get("invoice_number"), "PO:", ext.get("po_reference"))
        for rule in d["attempts"][-1].get("rules", []):
            if rule["result"] != "PASS":
                print("  FAIL rule:", rule["rule_name"], "-", rule["explanation"][:100])

print()
print("=== SM-05 INVESTIGATION: Reset baseline ===")
httpx.post(B + "/api/demo/reset", timeout=30)
import time; time.sleep(0.5)
dash = httpx.get(B + "/api/dashboard", timeout=10).json()
print("After reset: total_cases =", dash["total_cases"], "auto_approved =", dash["auto_approved"])
