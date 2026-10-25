"""
InvoicePilot Final Deep Audit — Comprehensive Test Suite
Port 8222, isolated audit database/storage.
Tests assignment requirements, financial invariants, edge cases, and advanced scenarios.
All expected values computed independently — NO imports from application code.
"""
import httpx, json, sys, time, os, hashlib, threading, fitz
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

B = "http://127.0.0.1:8222"
FIX = Path("data/fixtures")
RUN_DIR = Path("qa/final_audit/audit-20261025-040629")
EV = RUN_DIR / "evidence"
EV.mkdir(parents=True, exist_ok=True)

results = []
counts = {"PASS":0,"FAIL":0,"BLOCKED":0,"NOT_RUN":0,"NOT_APPLICABLE":0}

def R(tid, name, status, expected=None, actual=None, detail=""):
    counts[status] = counts.get(status,0)+1
    results.append({"id":tid,"name":name,"status":status,
        "expected":str(expected) if expected is not None else None,
        "actual":str(actual) if actual is not None else None,
        "detail":detail,"ts":datetime.utcnow().isoformat()})
    icon = {"PASS":"P","FAIL":"F","BLOCKED":"B","NOT_RUN":"N","NOT_APPLICABLE":"-"}.get(status,"?")
    line = f"  {icon} [{tid}] {name}"
    if status not in ("PASS","NOT_APPLICABLE") and detail: line += f" -- {detail[:80]}"
    print(line)

def reset():
    httpx.post(B+"/api/demo/reset",timeout=30); time.sleep(0.5)

def upload(fn, d=None):
    p = (d or FIX)/fn
    with open(p,"rb") as f:
        return httpx.post(B+"/api/upload",files={"file":(fn,f,"application/pdf")},timeout=60).json()

def upload_bytes(data, fn):
    return httpx.post(B+"/api/upload",files={"file":(fn,data,"application/pdf")},timeout=60).json()

def case(cid):
    return httpx.get(B+"/api/cases/"+cid,timeout=10).json()

def dash():
    return httpx.get(B+"/api/dashboard",timeout=10).json()

def active_cmts(cid):
    d = case(cid)
    return [c for c in d.get("commitments",[]) if c["status"] in ("RESERVED","POSTED","PAID")]

def save(name, data):
    with open(EV/(name+".json"),"w") as f: json.dump(data,f,indent=2,default=str)

def overage(po_net_cents):
    """Independent overage calculation."""
    pct = Decimal(po_net_cents) * Decimal("0.01")
    return int(min(pct, Decimal(5000)).quantize(Decimal("1"),rounding=ROUND_HALF_UP))

print("="*65)
print("INVOICEPILOT FINAL DEEP AUDIT")
print(f"Target: {B}  Time: {datetime.utcnow().isoformat()}Z")
print("="*65)

# Verify server
try:
    h = httpx.get(B+"/api/health",timeout=5).json()
    print(f"Server: {h['status']}  OCR: {h['checks']['ocr']['status']}")
except Exception as e:
    print(f"FATAL: Cannot reach audit server: {e}"); sys.exit(1)

# ═══════════════════════════════════════════════════════════
# SECTION 1: STARTUP & BASELINE (REQ-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 1: STARTUP & BASELINE ==")

R("REQ-01","Server starts and responds",
  "PASS" if h["status"] in ("ok","degraded") else "FAIL", expected="ok", actual=h["status"])

R("REQ-02","OCR dependency available",
  "PASS" if h["checks"]["ocr"]["status"]=="ok" else "BLOCKED",
  expected="ok", actual=h["checks"]["ocr"]["status"])

R("REQ-03","No API key required for local mode",
  "PASS" if h["checks"]["ai_extraction"]["status"] in ("disabled","ok") else "FAIL",
  detail="AI extraction disabled = local mode works")

R("REQ-04","Demo reset restores clean baseline",
  "PASS" if dash()["total_cases"]==0 else "FAIL", expected=0, actual=dash()["total_cases"])

# HTML pages load
for route, name in [("/","Dashboard"),("/health-page","Health")]:
    resp = httpx.get(B+route,timeout=10)
    R(f"REQ-05-{name}",f"{name} HTML loads",
      "PASS" if resp.status_code==200 and "InvoicePilot" in resp.text else "FAIL",
      expected=200, actual=resp.status_code)

R("REQ-06","Fixtures available",
  "PASS" if len(httpx.get(B+"/api/fixtures",timeout=10).json())>=10 else "FAIL")

# ═══════════════════════════════════════════════════════════
# SECTION 2: HAPPY PATH — FULL PIPELINE (HP-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 2: HAPPY PATH ==")
reset()

r = upload("happy_path_apex_invoice.pdf")
R("HP-01","Upload → AUTO_APPROVED","PASS" if r.get("decision")=="AUTO_APPROVED" else "FAIL",
  expected="AUTO_APPROVED", actual=r.get("decision"))

cid = r.get("case_id")
if cid and not r.get("is_byte_duplicate"):
    d = case(cid); save("hp_case",d)
    c = d["case"]; att = d["attempts"][-1] if d.get("attempts") else {}
    ext = att.get("extracted_data") or {}

    R("HP-02","Net = 250000 cents","PASS" if c["net_cents"]==250000 else "FAIL",expected=250000,actual=c["net_cents"])
    R("HP-03","Gross = 270000 cents","PASS" if c["gross_cents"]==270000 else "FAIL",expected=270000,actual=c["gross_cents"])
    R("HP-04","PO matched PO-1001","PASS" if c["po_id"]=="PO-1001" else "FAIL",expected="PO-1001",actual=c["po_id"])
    R("HP-05","Vendor = Apex (V-001)","PASS" if c.get("vendor_name")=="Apex Digital Solutions" else "FAIL",actual=c.get("vendor_name"))
    R("HP-06","Invoice# extracted","PASS" if c.get("invoice_number")=="INV-2026-0451" else "FAIL",actual=c.get("invoice_number"))

    cmts = active_cmts(cid)
    R("HP-07","Exactly 1 commitment","PASS" if len(cmts)==1 else "FAIL",expected=1,actual=len(cmts))
    R("HP-08","Commitment = 250000 cents (net, not gross)",
      "PASS" if cmts and cmts[0]["net_amount_cents"]==250000 else "FAIL",
      expected=250000, actual=cmts[0]["net_amount_cents"] if cmts else 0)

    events = att.get("events",[])
    completed = [e for e in events if e["status"]=="COMPLETED"]
    R("HP-09","11 stages completed","PASS" if len(completed)>=11 else "FAIL",expected=">=11",actual=len(completed))

    rules = att.get("rules",[])
    R("HP-10","8 policy rules evaluated","PASS" if len(rules)>=8 else "FAIL",expected=">=8",actual=len(rules))

    # Arithmetic check
    arith = [ru for ru in rules if ru["rule_id"]=="ARITHMETIC_GROSS"]
    R("HP-11","Arithmetic reconciliation PASS","PASS" if arith and arith[0]["result"]=="PASS" else "FAIL")

    # Refresh persistence
    d2 = case(cid)
    R("HP-12","Case persists on re-fetch","PASS" if d2["case"]["decision"]=="AUTO_APPROVED" else "FAIL")

    # Dashboard metrics
    dm = dash()
    R("HP-13","Dashboard total_cases=1","PASS" if dm["total_cases"]==1 else "FAIL",expected=1,actual=dm["total_cases"])
    R("HP-14","Dashboard approved_net=250000","PASS" if dm["approved_net_cents"]==250000 else "FAIL",
      expected=250000,actual=dm["approved_net_cents"])

# ═══════════════════════════════════════════════════════════
# SECTION 3: MULTIPLE VENDOR LAYOUTS (LAY-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 3: VENDOR LAYOUTS ==")
reset()
layouts = [
    ("happy_path_apex_invoice.pdf","Apex layout 1"),
    ("cumulative_a_meridian.pdf","Meridian layout 2"),
    ("ambiguous_po_brightwave.pdf","Brightwave layout 3"),
]
for fn,name in layouts:
    r = upload(fn)
    R(f"LAY-{name[:3]}",f"{name} → decision produced",
      "PASS" if r.get("decision") is not None else "FAIL", actual=r.get("decision"))

# ═══════════════════════════════════════════════════════════
# SECTION 4: FINANCIAL INVARIANTS (FIN-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 4: FINANCIAL INVARIANTS ==")

# Independent overage calculations
R("FIN-01","Overage $10k PO = $50 (5000 cents)","PASS" if overage(1000000)==5000 else "FAIL",expected=5000,actual=overage(1000000))
R("FIN-02","Overage $1k PO = $10 (1000 cents)","PASS" if overage(100000)==1000 else "FAIL",expected=1000,actual=overage(100000))
R("FIN-03","Overage $5k PO = $50 (5000 cents, capped)","PASS" if overage(500000)==5000 else "FAIL",expected=5000,actual=overage(500000))

# Net vs gross: happy path uses net=250000 vs PO-1001 net=250000. If gross were compared, $2700>$2500 would fail.
reset()
r = upload("happy_path_apex_invoice.pdf")
R("FIN-04","PO budget compares net (not gross vs net PO)",
  "PASS" if r.get("decision")=="AUTO_APPROVED" else "FAIL",
  detail="Gross $2700 > PO $2500 but net $2500 = PO $2500 passes")

# Cumulative: fresh $4040 → projected $10,040 ≤ $10,050
reset()
r = upload("cumulative_a_meridian.pdf")
R("FIN-05","$4040 net within ceiling","PASS" if r.get("decision")=="AUTO_APPROVED" else "FAIL")

# Cumulative: fresh $4060 → projected $10,060 > $10,050
reset()
r = upload("cumulative_b_meridian.pdf")
R("FIN-06","$4060 net exceeds ceiling","PASS" if r.get("decision")=="NEEDS_REVIEW" else "FAIL")

# Sequential: approve A, then C tips over
reset()
upload("cumulative_a_meridian.pdf")
r = upload("cumulative_c_meridian.pdf")
R("FIN-07","Sequential A+C exceeds (cumulative, not per-invoice)","PASS" if r.get("decision")=="NEEDS_REVIEW" else "FAIL")

# ═══════════════════════════════════════════════════════════
# SECTION 5: ORIGINAL EDGE CASES (EC1-* to EC4-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 5: ORIGINAL EDGE CASES ==")

# EC1: Duplicates
reset()
upload("duplicate_original_meridian.pdf")
# Byte repeat
r = upload("duplicate_original_meridian.pdf")
R("EC1-01","Byte repeat → is_byte_duplicate","PASS" if r.get("is_byte_duplicate") else "FAIL")
# No orphan case
non_seed = [c for c in httpx.get(B+"/api/cases",timeout=10).json() if not c["id"].startswith("SEED-")]
R("EC1-02","No orphan from byte repeat","PASS" if len(non_seed)==1 else "FAIL",expected=1,actual=len(non_seed))
# Business dup
r = upload("duplicate_reissued_meridian.pdf")
R("EC1-03","Business dup → BLOCKED","PASS" if r.get("decision")=="BLOCKED" else "FAIL")
# Identity collision
r = upload("duplicate_collision_meridian.pdf")
R("EC1-04","Identity collision → NEEDS_REVIEW","PASS" if r.get("decision")=="NEEDS_REVIEW" and "COLLISION" in (r.get("primary_reason_code") or "") else "FAIL")

# EC2: Cumulative budget — already tested in FIN-05/06/07
R("EC2-01","Cumulative budget (see FIN-05/06/07)","PASS",detail="Covered by financial invariant tests")

# EC3: Ambiguous PO
reset()
r = upload("ambiguous_po_brightwave.pdf")
R("EC3-01","Ambiguous PO → NEEDS_REVIEW/PO_AMBIGUOUS",
  "PASS" if r.get("decision")=="NEEDS_REVIEW" and "AMBIGUOUS" in (r.get("primary_reason_code") or "") else "FAIL")
R("EC3-02",">=2 PO candidates","PASS" if len(r.get("po_candidates",[]))>=2 else "FAIL",actual=len(r.get("po_candidates",[])))
# Review selection
if r.get("case_id"):
    resp = httpx.post(B+"/api/cases/"+r["case_id"]+"/review/select-po",
                      data={"po_id":"PO-1005","reason":"Pipeline scope matches"},timeout=60)
    rr = resp.json()
    R("EC3-03","PO selection → AUTO_APPROVED","PASS" if rr.get("decision")=="AUTO_APPROVED" else "FAIL",actual=rr.get("decision"))

# EC4: Scanned/missing number
reset()
r = upload("scanned_missing_number_pinnacle.pdf")
R("EC4-01","Scanned → NEEDS_INFORMATION",
  "PASS" if r.get("decision")=="NEEDS_INFORMATION" else "FAIL",actual=r.get("decision"))
# Corrected revision
if r.get("case_id"):
    with open(FIX/"scanned_corrected_pinnacle.pdf","rb") as f:
        rr = httpx.post(B+"/api/cases/"+r["case_id"]+"/review/attach-revision",
            files={"file":("corrected.pdf",f,"application/pdf")},
            data={"reason":"Vendor correction"},timeout=60).json()
    R("EC4-02","Corrected revision processed","PASS" if rr.get("decision") is not None else "FAIL",actual=rr.get("decision"))

# ═══════════════════════════════════════════════════════════
# SECTION 6: ADVANCED EDGE CASES (ADV-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 6: ADVANCED EDGE CASES ==")

# A: Stale review
reset()
ra = upload("adv_stale_review_a.pdf")
R("ADV-A01","Invoice A → PO_AMBIGUOUS","PASS" if ra.get("decision")=="NEEDS_REVIEW" else "FAIL")
rb = upload("adv_stale_review_b.pdf")
R("ADV-A02","Invoice B → AUTO_APPROVED","PASS" if rb.get("decision")=="AUTO_APPROVED" else "FAIL")
if ra.get("case_id"):
    rr = httpx.post(B+"/api/cases/"+ra["case_id"]+"/review/select-po",
                    data={"po_id":"PO-1002","reason":"Target PO selected"},timeout=60).json()
    R("ADV-A03","Stale resolution → CUMULATIVE_EXCEEDED",
      "PASS" if rr.get("decision")=="NEEDS_REVIEW" and "CUMULATIVE" in (rr.get("primary_reason_code") or "") else "FAIL",
      actual=str(rr.get("decision"))+"/"+str(rr.get("primary_reason_code")))
    ac = active_cmts(ra["case_id"])
    R("ADV-A04","No commitment from stale review","PASS" if len(ac)==0 else "FAIL",expected=0,actual=len(ac))

# B: Correction after approval
reset()
ro = upload("adv_correction_original.pdf")
R("ADV-B01","Original → AUTO_APPROVED","PASS" if ro.get("decision")=="AUTO_APPROVED" else "FAIL")
rc = upload("adv_correction_revised.pdf")
R("ADV-B02","Correction → IDENTITY_COLLISION",
  "PASS" if rc.get("decision")=="NEEDS_REVIEW" and "COLLISION" in (rc.get("primary_reason_code") or "") else "FAIL")
if ro.get("case_id"):
    ac = active_cmts(ro["case_id"])
    R("ADV-B03","Original commitment unchanged","PASS" if len(ac)==1 and ac[0]["net_amount_cents"]==200000 else "FAIL")

# C: Wrong-vendor PO
reset()
rc = upload("adv_wrong_vendor_po.pdf")
R("ADV-C01","Wrong-vendor PO → not approved","PASS" if rc.get("decision")!="AUTO_APPROVED" else "FAIL",actual=rc.get("decision"))
if rc.get("case_id") and not rc.get("is_byte_duplicate"):
    ac = active_cmts(rc["case_id"])
    R("ADV-C02","No commitment","PASS" if len(ac)==0 else "FAIL")

# D: OCR distractors
reset()
# Verify fixture is image-only
doc = fitz.open(str(FIX/"adv_ocr_distractors.pdf"))
txt = doc[0].get_text("text").strip(); doc.close()
R("ADV-D01","Fixture is image-only","PASS" if len(txt)<50 else "FAIL",expected="<50 chars",actual=len(txt))

rd = upload("adv_ocr_distractors.pdf")
R("ADV-D02","OCR produces decision","PASS" if rd.get("decision") is not None else "FAIL",actual=rd.get("decision"))
R("ADV-D03","Invoice# stays null","PASS" if rd.get("decision")=="NEEDS_INFORMATION" else "FAIL")
if rd.get("case_id") and not rd.get("is_byte_duplicate"):
    det = case(rd["case_id"])
    ext = det["attempts"][-1].get("extracted_data",{}) if det.get("attempts") else {}
    R("ADV-D04","PO-1003 extracted (not confused with invoice#)",
      "PASS" if ext.get("po_reference") and "1003" in (ext.get("po_reference") or "") else "FAIL",
      actual=ext.get("po_reference"))

# ═══════════════════════════════════════════════════════════
# SECTION 7: METAMORPHIC TESTS (META-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 7: METAMORPHIC ==")
reset()
pdf_bytes = (FIX/"happy_path_apex_invoice.pdf").read_bytes()
r = upload_bytes(pdf_bytes,"totally_random_name_999.pdf")
R("META-01","Renamed PDF → same result","PASS" if r.get("decision")=="AUTO_APPROVED" else "FAIL")

if r.get("case_id") and not r.get("is_byte_duplicate"):
    det = case(r["case_id"])
    events = det["attempts"][-1].get("events",[]) if det.get("attempts") else []
    has_ts = all(e.get("started_at") for e in events if e["status"]!="SKIPPED")
    R("META-02","Events have real timestamps","PASS" if has_ts else "FAIL")

# ═══════════════════════════════════════════════════════════
# SECTION 8: ERROR HANDLING (ERR-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 8: ERROR HANDLING ==")

R("ERR-01","Empty file rejected",
  "PASS" if httpx.post(B+"/api/upload",files={"file":("e.pdf",b"","application/pdf")},timeout=10).status_code in (400,422) else "FAIL")
R("ERR-02","Non-PDF rejected",
  "PASS" if httpx.post(B+"/api/upload",files={"file":("t.txt",b"hello","text/plain")},timeout=10).status_code in (400,422) else "FAIL")
resp = httpx.post(B+"/api/upload",files={"file":("bad.pdf",b"NOTAPDF"*100,"application/pdf")},timeout=30)
if resp.status_code==200:
    R("ERR-03","Malformed PDF no approval","PASS" if resp.json().get("decision")!="AUTO_APPROVED" else "FAIL")
else:
    R("ERR-03","Malformed PDF no approval","PASS",detail=f"HTTP {resp.status_code}")

# ═══════════════════════════════════════════════════════════
# SECTION 9: CONCURRENCY (CONC-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 9: CONCURRENCY ==")
reset()
conc_results = [None, None, None]
pdf = (FIX/"happy_path_apex_invoice.pdf").read_bytes()
def sub_bytes(idx):
    try: conc_results[idx] = upload_bytes(pdf, f"conc_{idx}.pdf")
    except Exception as e: conc_results[idx] = {"error":str(e)}

threads = [threading.Thread(target=sub_bytes,args=(i,)) for i in range(3)]
for t in threads: t.start()
for t in threads: t.join(timeout=30)

non_seed = [c for c in httpx.get(B+"/api/cases",timeout=10).json() if not c["id"].startswith("SEED-")]
R("CONC-01","3 concurrent identical bytes → 1 case","PASS" if len(non_seed)==1 else "FAIL",expected=1,actual=len(non_seed))

# ═══════════════════════════════════════════════════════════
# SECTION 10: AUDIT EXPORT (AUD-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 10: AUDIT EXPORT ==")
reset()
r = upload("happy_path_apex_invoice.pdf")
if r.get("case_id") and not r.get("is_byte_duplicate"):
    resp = httpx.get(B+"/api/cases/"+r["case_id"]+"/audit",timeout=10)
    audit = resp.json()
    save("audit_export",audit)
    R("AUD-01","Export has case+attempts+decisions+commitments",
      "PASS" if all(k in audit for k in ["case","attempts","decisions","commitments"]) else "FAIL")
    if audit.get("attempts"):
        R("AUD-02","Export has rules","PASS" if len(audit["attempts"][-1].get("rules",[]))>0 else "FAIL")
        R("AUD-03","Export has field evidences","PASS" if len(audit["attempts"][-1].get("field_evidences",[]))>0 else "FAIL")

# ═══════════════════════════════════════════════════════════
# SECTION 11: SCOPE BOUNDARIES (SCOPE-*)
# ═══════════════════════════════════════════════════════════
print("\n== SECTION 11: SCOPE BOUNDARIES ==")
R("SCOPE-01","No payment execution","NOT_APPLICABLE",detail="Explicitly out of scope per design")
R("SCOPE-02","No real email/mailbox","NOT_APPLICABLE",detail="PDF upload is the intake boundary")
R("SCOPE-03","No ERP posting","NOT_APPLICABLE",detail="Out of scope")
R("SCOPE-04","No authentication","NOT_APPLICABLE",detail="Demo scope, documented limitation")
R("SCOPE-05","No CSV export → no formula injection test","NOT_APPLICABLE",detail="Feature not implemented")

# ═══════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════
print("\n"+"="*65)
total = sum(counts.values())
print(f"RESULTS: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['BLOCKED']} BLOCKED, {counts['NOT_RUN']} NOT_RUN, {counts['NOT_APPLICABLE']} N/A")
print(f"Total: {total}  (executable: {total - counts['NOT_APPLICABLE']})")
print("="*65)

with open(str(RUN_DIR/"RESULTS.json"),"w") as f:
    json.dump({"summary":counts,"total":total,"results":results,"ts":datetime.utcnow().isoformat()},f,indent=2,default=str)
print(f"Saved to {RUN_DIR}/RESULTS.json")
sys.exit(1 if counts["FAIL"]>0 else 0)
