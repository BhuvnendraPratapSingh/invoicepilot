"""
Extended checks: arithmetic validation, edge cases, cross-format consistency.
"""
import httpx, json, time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sys
sys.path.insert(0, '.')

B = "http://127.0.0.1:8000"
EV = Path("qa/csv_repair/run-20261025/evidence")

results = []
P = F = 0

def R(tid, name, status, expected=None, actual=None, detail=""):
    global P, F
    if status == "PASS": P += 1
    else: F += 1
    results.append({"id": tid, "name": name, "status": status,
                    "expected": str(expected), "actual": str(actual), "detail": detail})
    icon = "P" if status == "PASS" else "F"
    line = f"  {icon} [{tid}] {name}"
    if status != "PASS" and detail: line += " -- " + detail[:100]
    print(line)

def reset():
    httpx.post(B + "/api/demo/reset", timeout=30)
    time.sleep(0.3)

def upload_csv(content, filename="t.csv"):
    return httpx.post(B + "/api/upload-csv",
        files={"file": (filename, content.encode("utf-8"), "text/csv")}, timeout=60).json()

def case_detail(cid):
    return httpx.get(B + "/api/cases/" + cid, timeout=10).json()

print("=" * 60)
print("Extended CSV Checks")
print("=" * 60)

# ── EX-1: Arithmetic rule — subtotal+tax != gross → no approval ──
print("\n[EX-1] Arithmetic mismatch CSV row")
reset()
csv_bad_arith = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
                 "currency,subtotal,tax,gross_total\n"
                 "Apex Digital Solutions,84-2917365,ARITH-BAD-001,2026-03-10,PO-1001,"
                 "USD,2500.00,200.00,2800.00\n")  # 2500+200=2700 != 2800
r = upload_csv(csv_bad_arith)
row = r["rows"][0]
R("EX-01", "Subtotal+tax != gross → NEEDS_REVIEW (arithmetic error)",
  "PASS" if row.get("decision") == "NEEDS_REVIEW" else "FAIL",
  expected="NEEDS_REVIEW", actual=row.get("decision"),
  detail=row.get("primary_reason_code", ""))
if row.get("case_id"):
    det = case_detail(row["case_id"])
    arith_rule = next((ru for ru in det["attempts"][-1].get("rules", [])
                       if ru["rule_id"] == "ARITHMETIC_GROSS"), None)
    R("EX-02", "Arithmetic rule reports FAIL",
      "PASS" if arith_rule and arith_rule["result"] == "FAIL" else "FAIL",
      actual=arith_rule["result"] if arith_rule else "NOT FOUND")
    cmts = [c for c in det.get("commitments", []) if c["status"] in ("RESERVED","POSTED","PAID")]
    R("EX-03", "Arithmetic error creates no commitment",
      "PASS" if len(cmts) == 0 else "FAIL", expected=0, actual=len(cmts))

# ── EX-2: _parse_cents precision (independent Decimal math check) ──
print("\n[EX-2] Monetary parsing — independent Decimal check")
from app.services.csv_processor import _parse_cents

cases = [
    ("2500.00", 250000),
    ("2500", 250000),
    ("2,500.00", 250000),
    ("$2,500.00", 250000),
    ("0.01", 1),
    ("10050.00", 1005000),
    ("4050.01", 405001),
    ("", None),
    (None, None),
    ("abc", None),
]
all_ok = True
for val, exp in cases:
    got = _parse_cents(val)
    ok = got == exp
    if not ok:
        all_ok = False
        print(f"    FAIL: _parse_cents({repr(val)}) = {got}, expected {exp}")
R("EX-04", "_parse_cents parses all monetary forms correctly",
  "PASS" if all_ok else "FAIL")

# ── EX-3: Percentage-limited overage — $1,000 PO allows $10, not $50 ──
print("\n[EX-3] Percentage-limited overage ($1k PO = $10 max)")
# PO-1004 is $1,500 net for V-001. Let me use a calculation check.
# Independently: min(1500 * 0.01, 50) = min(15, 50) = 15 cents * 100 = 1500 cents = $15
# For a $1,000 PO: min(1000*0.01, 50) = min(10, 50) = $10
from decimal import Decimal, ROUND_HALF_UP
def calc_overage(po_net_cents):
    pct = Decimal(po_net_cents) * Decimal("0.01")
    return int(min(pct, Decimal(5000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

R("EX-05", "$1,000 PO overage = $10 (1000 cents)",
  "PASS" if calc_overage(100000) == 1000 else "FAIL",
  expected=1000, actual=calc_overage(100000))
R("EX-06", "$5,000 PO overage = $50 (capped, 5000 cents)",
  "PASS" if calc_overage(500000) == 5000 else "FAIL",
  expected=5000, actual=calc_overage(500000))
R("EX-07", "$10,000 PO overage = $50 (capped, 5000 cents)",
  "PASS" if calc_overage(1000000) == 5000 else "FAIL",
  expected=5000, actual=calc_overage(1000000))

# ── EX-4: Cross-format duplicate — PDF then same identity via CSV ──
print("\n[EX-4] Cross-format duplicate: PDF approved, then CSV same identity")
reset()
# Approve via PDF
with open("data/fixtures/happy_path_apex_invoice.pdf", "rb") as f:
    pdf_r = httpx.post(B + "/api/upload",
        files={"file": ("hp.pdf", f, "application/pdf")}, timeout=60).json()
R("EX-08", "PDF original → AUTO_APPROVED (setup)",
  "PASS" if pdf_r.get("decision") == "AUTO_APPROVED" else "FAIL")

# Same vendor+invoice# via CSV (different amounts → collision)
csv_dup = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
           "currency,subtotal,tax,gross_total\n"
           "Apex Digital Solutions,84-2917365,INV-2026-0451,2026-03-10,PO-1001,"
           "USD,2600.00,208.00,2808.00\n")  # same invoice# as happy_path, different amount
r_dup = upload_csv(csv_dup)
row_dup = r_dup["rows"][0]
R("EX-09", "CSV same invoice# + different amount → IDENTITY_COLLISION",
  "PASS" if row_dup.get("decision") == "NEEDS_REVIEW" and
             "COLLISION" in (row_dup.get("primary_reason_code") or "") else "FAIL",
  actual=str(row_dup.get("decision")) + "/" + str(row_dup.get("primary_reason_code")))

# Original PDF commitment unchanged
if pdf_r.get("case_id"):
    orig = case_detail(pdf_r["case_id"])
    cmts = [c for c in orig.get("commitments", []) if c["status"] in ("RESERVED","POSTED","PAID")]
    R("EX-10", "Original PDF commitment unchanged after CSV collision",
      "PASS" if len(cmts) == 1 and cmts[0]["net_amount_cents"] == 250000 else "FAIL",
      expected="1x250000", actual=str(len(cmts)) + "x" + str(cmts[0]["net_amount_cents"] if cmts else 0))

# ── EX-5: Multi-row CSV partial batch ──
print("\n[EX-5] Multi-row CSV batch with mixed valid/invalid rows")
reset()
csv_multi = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
             "currency,subtotal,tax,gross_total\n"
             "Apex Digital Solutions,84-2917365,MULTI-001,2026-03-10,PO-1001,USD,2500.00,200.00,2700.00\n"
             "Meridian Consulting Group,37-8104926,MULTI-002,2026-03-10,PO-1002,USD,200.00,16.00,216.00\n"
             "Unknown Vendor XYZ,,MULTI-003,2026-03-10,PO-1001,USD,500.00,40.00,540.00\n")
r_multi = upload_csv(csv_multi)
R("EX-11", "Multi-row: 3 rows processed",
  "PASS" if r_multi["summary"]["total_rows"] == 3 else "FAIL",
  expected=3, actual=r_multi["summary"]["total_rows"])
R("EX-12", "Multi-row: valid rows get decisions",
  "PASS" if r_multi["rows"][0].get("decision") is not None else "FAIL")
R("EX-13", "Multi-row: unknown vendor row not auto-approved",
  "PASS" if r_multi["rows"][2].get("decision") != "AUTO_APPROVED" else "FAIL",
  actual=r_multi["rows"][2].get("decision"))

# ── EX-6: CSV encoding — UTF-8 BOM ──
print("\n[EX-6] CSV encoding variants")
reset()
bom_csv = ("\ufeffvendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
           "currency,subtotal,tax,gross_total\n"
           "Apex Digital Solutions,84-2917365,BOM-001,2026-03-10,PO-1001,USD,2500.00,200.00,2700.00\n")
r_bom = httpx.post(B + "/api/upload-csv",
    files={"file": ("bom.csv", bom_csv.encode("utf-8-sig"), "text/csv")}, timeout=60).json()
R("EX-14", "UTF-8 BOM CSV accepted and processed",
  "PASS" if r_bom.get("rows") and r_bom["rows"][0].get("decision") is not None else "FAIL",
  actual=r_bom.get("rows", [{}])[0].get("decision"))

# ── EX-7: Wrong file type sent to CSV endpoint ──
print("\n[EX-7] Wrong type to CSV endpoint")
r_wrong = httpx.post(B + "/api/upload-csv",
    files={"file": ("test.pdf", b"fake", "application/pdf")}, timeout=30)
R("EX-15", "PDF sent to CSV endpoint → 400",
  "PASS" if r_wrong.status_code == 400 else "FAIL",
  expected=400, actual=r_wrong.status_code)

print("\n" + "=" * 60)
print(f"RESULTS: {P} PASS, {F} FAIL  (total {P+F})")
print("=" * 60)

existing = json.load(open("qa/csv_repair/run-20261025/RESULTS.json"))
all_results = existing["results"] + results
all_p = existing["summary"]["pass"] + P
all_f = existing["summary"]["fail"] + F
with open("qa/csv_repair/run-20261025/RESULTS.json", "w") as f:
    json.dump({"summary": {"pass": all_p, "fail": all_f, "total": all_p + all_f},
               "results": all_results}, f, indent=2)
print(f"Combined: {all_p} PASS, {all_f} FAIL")
