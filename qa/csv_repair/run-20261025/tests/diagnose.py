"""
CSV Repair Diagnostic Script
Runs against port 8000. Records all findings.
"""
import httpx, json, time
from pathlib import Path

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
    if status != "PASS" and detail:
        line += " -- " + detail[:80]
    print(line)

def reset():
    httpx.post(B + "/api/demo/reset", timeout=30)
    time.sleep(0.3)

def upload_csv_str(content, filename="test.csv"):
    return httpx.post(B + "/api/upload-csv",
        files={"file": (filename, content.encode("utf-8"), "text/csv")}, timeout=60).json()

def upload_pdf(fn):
    with open("data/fixtures/" + fn, "rb") as f:
        return httpx.post(B + "/api/upload",
            files={"file": (fn, f, "application/pdf")}, timeout=60).json()

def case_detail(cid):
    return httpx.get(B + "/api/cases/" + cid, timeout=10).json()

print("=" * 60)
print("CSV Repair Diagnostic")
print("=" * 60)

# ══════════════════════════════════════
# DIAG-1: Does a valid CSV row approve when it should?
# Same facts as happy-path PDF: Apex V-001, PO-1001, $2500 net
# ══════════════════════════════════════
print("\n[DIAG-1] Valid CSV row — financial correctness")
reset()
csv = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
       "currency,subtotal,tax,gross_total,description\n"
       "Apex Digital Solutions,84-2917365,CSV-V1-001,2026-03-10,PO-1001,"
       "USD,2500.00,200.00,2700.00,Website redesign\n")
r = upload_csv_str(csv)
row = r["rows"][0]
R("D1-01", "Valid CSV row → AUTO_APPROVED",
  "PASS" if row.get("decision") == "AUTO_APPROVED" else "FAIL",
  expected="AUTO_APPROVED", actual=row.get("decision"))

if row.get("case_id"):
    det = case_detail(row["case_id"])
    att = det["attempts"][-1] if det.get("attempts") else {}
    rules = att.get("rules", [])
    failing = [ru for ru in rules if ru["result"] == "FAIL"]
    R("D1-02", "No failing rules", "PASS" if not failing else "FAIL",
      detail="; ".join(ru["rule_id"] for ru in failing))
    cmts = [c for c in det.get("commitments", []) if c["status"] in ("RESERVED","POSTED","PAID")]
    R("D1-03", "Commitment = 250000 cents (net)",
      "PASS" if len(cmts) == 1 and cmts[0]["net_amount_cents"] == 250000 else "FAIL",
      expected="1x250000", actual=str(len(cmts)) + "x" + str(cmts[0]["net_amount_cents"] if cmts else 0))
    # Save evidence
    with open(EV / "d1_case_detail.json", "w") as f:
        json.dump(det, f, indent=2, default=str)

# ══════════════════════════════════════
# DIAG-2: CSV vs PDF agreement on same facts
# ══════════════════════════════════════
print("\n[DIAG-2] CSV vs PDF: same facts → same decision")
reset()
pdf_r = upload_pdf("happy_path_apex_invoice.pdf")
R("D2-01", "PDF happy path → AUTO_APPROVED",
  "PASS" if pdf_r.get("decision") == "AUTO_APPROVED" else "FAIL",
  actual=pdf_r.get("decision"))

reset()
csv2 = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
        "currency,subtotal,tax,gross_total,description\n"
        "Apex Digital Solutions,84-2917365,INV-2026-0452,2026-03-10,PO-1001,"
        "USD,2500.00,200.00,2700.00,Website redesign\n")
csv_r2 = upload_csv_str(csv2)
row2 = csv_r2["rows"][0]
R("D2-02", "CSV same facts → AUTO_APPROVED (parity with PDF)",
  "PASS" if row2.get("decision") == "AUTO_APPROVED" else "FAIL",
  expected="AUTO_APPROVED", actual=row2.get("decision"))

# ══════════════════════════════════════
# DIAG-3: Financial invariants via CSV
# ══════════════════════════════════════
print("\n[DIAG-3] Financial invariants via CSV")

# $4,050 at exact ceiling
reset()
csv3 = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
        "currency,subtotal,tax,gross_total\n"
        "Meridian Consulting Group,37-8104926,CSV-CEIL-001,2026-03-10,PO-1002,"
        "USD,4050.00,324.00,4374.00\n")
r3 = upload_csv_str(csv3)
R("D3-01", "$4,050 exact ceiling → AUTO_APPROVED",
  "PASS" if r3["rows"][0].get("decision") == "AUTO_APPROVED" else "FAIL",
  actual=r3["rows"][0].get("decision"),
  detail=r3["rows"][0].get("primary_reason_code", ""))

# $4,050.01 one cent over
reset()
csv4 = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
        "currency,subtotal,tax,gross_total\n"
        "Meridian Consulting Group,37-8104926,CSV-OVER-001,2026-03-10,PO-1002,"
        "USD,4050.01,324.0008,4374.0108\n")
r4 = upload_csv_str(csv4)
R("D3-02", "$4,050.01 one cent over → NEEDS_REVIEW",
  "PASS" if r4["rows"][0].get("decision") == "NEEDS_REVIEW" else "FAIL",
  actual=r4["rows"][0].get("decision"))
if r4["rows"][0].get("case_id"):
    det4 = case_detail(r4["rows"][0]["case_id"])
    cmts4 = [c for c in det4.get("commitments",[]) if c["status"] in ("RESERVED","POSTED","PAID")]
    R("D3-03", "Over-ceiling CSV row has no commitment",
      "PASS" if len(cmts4) == 0 else "FAIL", expected=0, actual=len(cmts4))

# ══════════════════════════════════════
# DIAG-4: CSV duplicate detection
# ══════════════════════════════════════
print("\n[DIAG-4] CSV duplicate detection")
reset()
# Approve original via PDF
pdf_orig = upload_pdf("duplicate_original_meridian.pdf")
R("D4-00", "Setup: PDF original approved",
  "PASS" if pdf_orig.get("decision") == "AUTO_APPROVED" else "FAIL")

# Submit same business identity via CSV (different amounts → collision)
csv5 = ("vendor_name,vendor_tax_id,invoice_number,invoice_date,po_reference,"
        "currency,subtotal,tax,gross_total\n"
        "Meridian Consulting Group,37-8104926,MCG-2026-0088,2026-02-15,PO-1002,"
        "USD,3800.00,304.00,4104.00\n")  # same invoice# but different amounts
r5 = upload_csv_str(csv5)
row5 = r5["rows"][0]
R("D4-01", "CSV same invoice# + different amounts → IDENTITY_COLLISION",
  "PASS" if row5.get("decision") == "NEEDS_REVIEW" and
             "COLLISION" in (row5.get("primary_reason_code") or "") else "FAIL",
  actual=str(row5.get("decision")) + "/" + str(row5.get("primary_reason_code")))

# ══════════════════════════════════════
# DIAG-5: CSV error handling
# ══════════════════════════════════════
print("\n[DIAG-5] CSV error handling")

# Empty file
r_empty = httpx.post(B + "/api/upload-csv",
    files={"file": ("e.csv", b"", "text/csv")}, timeout=30)
R("D5-01", "Empty CSV rejected", "PASS" if r_empty.status_code in (400, 422) else "FAIL",
  expected="400/422", actual=r_empty.status_code)

# Missing required column
r_miss = upload_csv_str("vendor_name,invoice_date\nApex,2026-03-10\n")
R("D5-02", "Missing invoice_number → row error (not crash)",
  "PASS" if r_miss.get("rows") and r_miss["rows"][0].get("error") else "FAIL",
  detail=r_miss.get("rows", [{}])[0].get("error", "no error field"))

# Unknown vendor
reset()
r_unk = upload_csv_str(
    "vendor_name,invoice_number,invoice_date,currency,subtotal,gross_total\n"
    "Totally Unknown Vendor XYZ,UNK-001,2026-03-10,USD,500.00,540.00\n")
row_unk = r_unk["rows"][0]
R("D5-03", "Unknown vendor → not AUTO_APPROVED",
  "PASS" if row_unk.get("decision") != "AUTO_APPROVED" else "FAIL",
  actual=row_unk.get("decision"))
if row_unk.get("case_id"):
    det_unk = case_detail(row_unk["case_id"])
    cmts_unk = [c for c in det_unk.get("commitments",[]) if c["status"] in ("RESERVED","POSTED","PAID")]
    R("D5-04", "Unknown vendor CSV row has no commitment",
      "PASS" if len(cmts_unk) == 0 else "FAIL", expected=0, actual=len(cmts_unk))

# ══════════════════════════════════════
# DIAG-6: setupUpload JS null-pointer risk
# ══════════════════════════════════════
print("\n[DIAG-6] Frontend upload area element check")
r_html = httpx.get(B + "/", timeout=10)
has_upload_area = 'id="uploadArea"' in r_html.text
has_csv_input = 'id="csvFileInput"' in r_html.text
has_file_input = 'id="fileInput"' in r_html.text
R("D6-01", "uploadArea element present in HTML",
  "PASS" if has_upload_area else "FAIL")
R("D6-02", "csvFileInput element present in HTML",
  "PASS" if has_csv_input else "FAIL")
R("D6-03", "fileInput element present in HTML",
  "PASS" if has_file_input else "FAIL")

# ══════════════════════════════════════
# DIAG-7: PDF upload still works after CSV addition
# ══════════════════════════════════════
print("\n[DIAG-7] PDF upload regression")
reset()
r_pdf = upload_pdf("happy_path_apex_invoice.pdf")
R("D7-01", "PDF happy path still AUTO_APPROVED",
  "PASS" if r_pdf.get("decision") == "AUTO_APPROVED" else "FAIL",
  actual=r_pdf.get("decision"))
R("D7-02", "PDF returns JSON (not HTML error)",
  "PASS", detail="covered by D7-01")

print("\n" + "=" * 60)
print(f"RESULTS: {P} PASS, {F} FAIL  (total {P+F})")
print("=" * 60)

with open("qa/csv_repair/run-20261025/RESULTS.json", "w") as f:
    json.dump({"summary": {"pass": P, "fail": F}, "results": results}, f, indent=2)
print("Saved RESULTS.json")
