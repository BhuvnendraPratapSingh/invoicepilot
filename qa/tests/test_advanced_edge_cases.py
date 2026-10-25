"""
Advanced edge-case test suite: Scenarios A-D
Runs against isolated QA server on port 8111.
"""
import httpx, json, time, sys, os
from pathlib import Path
from datetime import datetime

B = "http://127.0.0.1:8111"
FIX = Path("data/fixtures")
EV = Path("qa/evidence/advanced_edge_cases")
EV.mkdir(parents=True, exist_ok=True)

results = []
P, F, BL = 0, 0, 0

def R(tid, name, status, expected=None, actual=None, detail=""):
    global P, F, BL
    results.append({"id":tid,"name":name,"status":status,"expected":str(expected) if expected else None,
                     "actual":str(actual) if actual else None,"detail":detail,"ts":datetime.utcnow().isoformat()})
    if status=="PASS": P+=1
    elif status=="FAIL": F+=1
    elif status=="BLOCKED": BL+=1
    icon = {"PASS":"P","FAIL":"F","BLOCKED":"B"}.get(status,"?")
    line = f"  {icon} [{tid}] {name}"
    if status!="PASS" and detail: line += f" — {detail}"
    print(line)

def reset():
    httpx.post(B+"/api/demo/reset", timeout=30); time.sleep(0.5)

def upload(fn):
    with open(FIX/fn,"rb") as f:
        return httpx.post(B+"/api/upload",files={"file":(fn,f,"application/pdf")},timeout=60).json()

def case(cid):
    return httpx.get(B+"/api/cases/"+cid,timeout=10).json()

def active_commitments(cid):
    d = case(cid)
    return [c for c in d.get("commitments",[]) if c["status"] in ("RESERVED","POSTED","PAID")]

def po_committed(po_id):
    """Get total active committed cents for a PO from all non-seed cases."""
    cases_list = httpx.get(B+"/api/cases",timeout=10).json()
    total = 0
    for cs in cases_list:
        if cs.get("po_id")==po_id:
            det = case(cs["id"])
            for c in det.get("commitments",[]):
                if c["status"] in ("RESERVED","POSTED","PAID") and c["po_id"]==po_id:
                    total += c["net_amount_cents"]
    return total

def save(name, data):
    with open(EV/(name+".json"),"w") as f: json.dump(data,f,indent=2,default=str)

print("="*60)
print("Advanced Edge-Case Test Suite")
print("Target:", B)
print("="*60)

# ═══════════════════════════════════════════════
# SCENARIO A: Stale review
# ═══════════════════════════════════════════════
def test_scenario_a():
    print("\n== SCENARIO A: Stale review (PO balance changes before resolution) ==")
    reset()

    # A-01: Upload Invoice A (V-002, no PO ref) → NEEDS_REVIEW / PO_AMBIGUOUS
    ra = upload("adv_stale_review_a.pdf")
    R("A-01","Invoice A → NEEDS_REVIEW/PO_AMBIGUOUS",
      "PASS" if ra.get("decision")=="NEEDS_REVIEW" and "AMBIGUOUS" in (ra.get("primary_reason_code") or "") else "FAIL",
      expected="NEEDS_REVIEW/PO_AMBIGUOUS",
      actual=str(ra.get("decision"))+"/"+str(ra.get("primary_reason_code")))
    cid_a = ra.get("case_id")

    # A-02: Invoice A has no commitment
    if cid_a:
        ac = active_commitments(cid_a)
        R("A-02","Invoice A has 0 active commitments",
          "PASS" if len(ac)==0 else "FAIL", expected=0, actual=len(ac))

    # A-03: Upload Invoice B (V-002, PO-1002, $200 net) → AUTO_APPROVED
    rb = upload("adv_stale_review_b.pdf")
    R("A-03","Invoice B → AUTO_APPROVED",
      "PASS" if rb.get("decision")=="AUTO_APPROVED" else "FAIL",
      expected="AUTO_APPROVED", actual=rb.get("decision"))
    cid_b = rb.get("case_id")

    # A-04: Invoice B committed $200
    if cid_b:
        ac_b = active_commitments(cid_b)
        R("A-04","Invoice B has 1 commitment of $200 (20000 cents)",
          "PASS" if len(ac_b)==1 and ac_b[0]["net_amount_cents"]==20000 else "FAIL",
          expected="1 x 20000", actual=str(len(ac_b))+" x "+str(ac_b[0]["net_amount_cents"] if ac_b else 0))
        save("a04_invoice_b", case(cid_b))

    # A-05: Now resolve A by selecting PO-1002. Re-evaluation should see $6,200 committed.
    # Projected = $6,200 + $4,000 = $10,200 > $10,050 ceiling → NEEDS_REVIEW
    if cid_a:
        form = {"po_id":"PO-1002","reason":"QA test: selecting target PO after balance changed"}
        resp = httpx.post(B+"/api/cases/"+cid_a+"/review/select-po",data=form,timeout=60)
        rr = resp.json()
        R("A-05","Stale review resolution → NEEDS_REVIEW/PO_CUMULATIVE_LIMIT_EXCEEDED",
          "PASS" if rr.get("decision")=="NEEDS_REVIEW" and "CUMULATIVE" in (rr.get("primary_reason_code") or "") else "FAIL",
          expected="NEEDS_REVIEW/PO_CUMULATIVE_LIMIT_EXCEEDED",
          actual=str(rr.get("decision"))+"/"+str(rr.get("primary_reason_code")),
          detail=rr.get("explanation","")[:120] if rr.get("decision")!="NEEDS_REVIEW" else "")
        save("a05_stale_resolution", rr)

    # A-06: Invoice A still has no commitment after failed review
    if cid_a:
        ac_a2 = active_commitments(cid_a)
        R("A-06","Invoice A still has 0 commitments after review",
          "PASS" if len(ac_a2)==0 else "FAIL", expected=0, actual=len(ac_a2))

    # A-07: Review action preserved in history
    if cid_a:
        det = case(cid_a)
        reviews = det.get("review_actions",[])
        R("A-07","Review action recorded",
          "PASS" if len(reviews)>=1 and reviews[-1].get("action_type")=="SELECT_PO" else "FAIL",
          expected=">=1 SELECT_PO", actual=str(len(reviews)))
        save("a07_full_case_a", det)

    # A-08: Audit export includes both attempts
    if cid_a:
        det = case(cid_a)
        atts = det.get("attempts",[])
        R("A-08","Case A has >=2 processing attempts",
          "PASS" if len(atts)>=2 else "FAIL", expected=">=2", actual=len(atts))

# ═══════════════════════════════════════════════
# SCENARIO B: Correction after approval
# ═══════════════════════════════════════════════
def test_scenario_b():
    print("\n== SCENARIO B: Correction arrives after original approved ==")
    reset()

    # B-01: Upload original ADV-CORR-1042 → AUTO_APPROVED
    ro = upload("adv_correction_original.pdf")
    R("B-01","Original → AUTO_APPROVED",
      "PASS" if ro.get("decision")=="AUTO_APPROVED" else "FAIL",
      expected="AUTO_APPROVED", actual=ro.get("decision"))
    cid_o = ro.get("case_id")

    # B-02: Original has $2,000 commitment
    if cid_o:
        ac = active_commitments(cid_o)
        R("B-02","Original commitment = $2,000 (200000 cents)",
          "PASS" if len(ac)==1 and ac[0]["net_amount_cents"]==200000 else "FAIL",
          expected="1 x 200000", actual=str(len(ac))+" x "+str(ac[0]["net_amount_cents"] if ac else 0))

    # B-03: Upload correction (same invoice#, different amount) → NEEDS_REVIEW/IDENTITY_COLLISION
    rc = upload("adv_correction_revised.pdf")
    R("B-03","Correction → NEEDS_REVIEW/INVOICE_IDENTITY_COLLISION",
      "PASS" if rc.get("decision")=="NEEDS_REVIEW" and "IDENTITY_COLLISION" in (rc.get("primary_reason_code") or "") else "FAIL",
      expected="NEEDS_REVIEW/INVOICE_IDENTITY_COLLISION",
      actual=str(rc.get("decision"))+"/"+str(rc.get("primary_reason_code")))
    cid_c = rc.get("case_id")
    save("b03_correction_result", rc)

    # B-04: Original commitment unchanged (still $2,000, still 1 commitment)
    if cid_o:
        ac2 = active_commitments(cid_o)
        R("B-04","Original commitment unchanged after correction attempt",
          "PASS" if len(ac2)==1 and ac2[0]["net_amount_cents"]==200000 else "FAIL",
          expected="1 x 200000", actual=str(len(ac2))+" x "+str(ac2[0]["net_amount_cents"] if ac2 else 0))

    # B-05: Correction case has NO commitment
    if cid_c and cid_c != cid_o:
        ac_c = active_commitments(cid_c)
        R("B-05","Correction case has 0 commitments",
          "PASS" if len(ac_c)==0 else "FAIL", expected=0, actual=len(ac_c))
    elif cid_c == cid_o:
        R("B-05","Correction linked to original case (same case_id)",
          "PASS", detail="collision detected within same vendor+invoice identity")

    # B-06: Re-uploading correction bytes is idempotent
    rc2 = upload("adv_correction_revised.pdf")
    is_byte_dup = rc2.get("is_byte_duplicate")
    R("B-06","Re-upload correction → byte duplicate (no extra liability)",
      "PASS" if is_byte_dup else "FAIL", expected="is_byte_duplicate=True", actual=str(is_byte_dup))

    # B-07: Re-uploading original with same data → BLOCKED (duplicate of approved)
    ro2 = upload("adv_correction_original.pdf")
    is_dup = ro2.get("is_byte_duplicate")
    R("B-07","Re-upload original → byte duplicate",
      "PASS" if is_dup else "FAIL", expected="is_byte_duplicate=True", actual=str(is_dup))

# ═══════════════════════════════════════════════
# SCENARIO C: PO belongs to another vendor
# ═══════════════════════════════════════════════
def test_scenario_c():
    print("\n== SCENARIO C: PO belongs to another vendor ==")
    reset()

    # C-01: Upload invoice from Apex (V-001) citing PO-1002 (belongs to V-002)
    rc = upload("adv_wrong_vendor_po.pdf")
    R("C-01","Wrong-vendor PO → NOT AUTO_APPROVED",
      "PASS" if rc.get("decision")!="AUTO_APPROVED" else "FAIL",
      expected="NOT AUTO_APPROVED", actual=rc.get("decision"))

    cid = rc.get("case_id")

    # C-02: No commitment created
    if cid and not rc.get("is_byte_duplicate"):
        ac = active_commitments(cid)
        R("C-02","No commitment created",
          "PASS" if len(ac)==0 else "FAIL", expected=0, actual=len(ac))

    # C-03: Reason mentions PO mismatch
    if cid and not rc.get("is_byte_duplicate"):
        det = case(cid)
        att = det["attempts"][-1] if det.get("attempts") else {}
        po_event = next((e for e in att.get("events",[]) if e["stage_name"]=="po_matching" and e["status"]=="COMPLETED"), None)
        has_mismatch = po_event and "belongs to vendor" in (po_event.get("message") or "")
        msg = (po_event.get("message") or "") if po_event else "no po_matching event"
        R("C-03","PO matching explains vendor mismatch",
          "PASS" if has_mismatch else "FAIL",
          detail=msg[:100])
        save("c03_wrong_vendor", det)

    # C-04: Control test — same invoice referencing Apex's own PO-1001 succeeds
    reset()
    r_ok = upload("happy_path_apex_invoice.pdf")
    R("C-04","Same vendor's PO → AUTO_APPROVED (control)",
      "PASS" if r_ok.get("decision")=="AUTO_APPROVED" else "FAIL",
      expected="AUTO_APPROVED", actual=r_ok.get("decision"))

# ═══════════════════════════════════════════════
# SCENARIO D: OCR with distractor identifiers
# ═══════════════════════════════════════════════
def test_scenario_d():
    print("\n== SCENARIO D: OCR reads identifiers, but none is an invoice number ==")

    # Check OCR availability
    h = httpx.get(B+"/api/health",timeout=5).json()
    ocr_ok = h.get("checks",{}).get("ocr",{}).get("status")=="ok"
    if not ocr_ok:
        R("D-01","OCR available","BLOCKED",detail="Tesseract not available")
        return

    reset()

    # D-01: Verify fixture has no usable native text
    import fitz
    doc = fitz.open(str(FIX / "adv_ocr_distractors.pdf"))
    text = doc[0].get_text("text").strip()
    doc.close()
    R("D-01","Fixture has <50 chars native text",
      "PASS" if len(text)<50 else "FAIL", expected="<50", actual=len(text))

    # D-02: Upload scanned invoice with distractors
    rd = upload("adv_ocr_distractors.pdf")
    R("D-02","OCR scan produces a decision (not technical failure)",
      "PASS" if rd.get("decision") is not None else "FAIL",
      expected="a decision", actual=rd.get("decision"))
    cid = rd.get("case_id")

    if cid and not rd.get("is_byte_duplicate") and rd.get("decision") is not None:
        det = case(cid)
        att = det["attempts"][-1] if det.get("attempts") else {}
        ext = att.get("extracted_data") or {}
        save("d02_ocr_result", det)

        # D-03: Invoice number is null (not confused with account# or service ref)
        R("D-03","Invoice number is null (not fabricated from distractors)",
          "PASS" if ext.get("invoice_number") is None else "FAIL",
          expected="None", actual=ext.get("invoice_number"))

        # D-04: Decision is NEEDS_INFORMATION
        R("D-04","Decision = NEEDS_INFORMATION/MISSING_*",
          "PASS" if rd.get("decision")=="NEEDS_INFORMATION" and "MISSING" in (rd.get("primary_reason_code") or "") else "FAIL",
          expected="NEEDS_INFORMATION", actual=str(rd.get("decision"))+"/"+str(rd.get("primary_reason_code")))

        # D-05: No commitment
        ac = active_commitments(cid)
        R("D-05","No commitment for missing-info case",
          "PASS" if len(ac)==0 else "FAIL", expected=0, actual=len(ac))

        # D-06: PO reference extracted correctly (not confused with invoice#)
        R("D-06","PO reference extracted (not confused with invoice number)",
          "PASS" if ext.get("po_reference") and "1003" in (ext.get("po_reference") or "") else "FAIL",
          expected="PO-1003", actual=ext.get("po_reference"))

        # D-07: Attach corrected version with real invoice number
        with open(FIX/"adv_ocr_distractors_corrected.pdf","rb") as f:
            rr = httpx.post(B+"/api/cases/"+cid+"/review/attach-revision",
                files={"file":("corrected.pdf",f,"application/pdf")},
                data={"reason":"Vendor added invoice number"},timeout=60).json()
        R("D-07","Corrected revision processed",
          "PASS" if rr.get("decision") is not None else "FAIL",
          expected="a decision", actual=rr.get("decision"))

        # D-08: Corrected version extracts real invoice number
        if rr.get("case_id"):
            det2 = case(rr["case_id"])
            att2 = det2["attempts"][-1] if det2.get("attempts") else {}
            ext2 = att2.get("extracted_data") or {}
            R("D-08","Corrected version extracts invoice number",
              "PASS" if ext2.get("invoice_number") and "PCS-ADV" in (ext2.get("invoice_number") or "") else "FAIL",
              expected="PCS-ADV-2026-0099", actual=ext2.get("invoice_number"))
            save("d08_corrected", det2)

        # D-09: History preserved (>=2 attempts)
        det3 = case(cid)
        atts = det3.get("attempts",[])
        R("D-09","History preserved (>=2 attempts)",
          "PASS" if len(atts)>=2 else "FAIL", expected=">=2", actual=len(atts))

    else:
        for tid in ["D-03","D-04","D-05","D-06","D-07","D-08","D-09"]:
            R(tid,"OCR scenario","BLOCKED",detail="No case from OCR upload")

# ═══════════════════════════════════════════════
# REGRESSION: Run existing edge-case families
# ═══════════════════════════════════════════════
def test_regression():
    print("\n== REGRESSION: Original 4 edge-case families ==")
    reset()

    # Happy path
    r = upload("happy_path_apex_invoice.pdf")
    R("REG-01","Happy path → AUTO_APPROVED",
      "PASS" if r.get("decision")=="AUTO_APPROVED" else "FAIL")

    # Duplicates
    upload("duplicate_original_meridian.pdf")
    rd = upload("duplicate_reissued_meridian.pdf")
    R("REG-02","Reissued dup → BLOCKED",
      "PASS" if rd.get("decision")=="BLOCKED" else "FAIL")

    # Cumulative
    reset()
    ra = upload("cumulative_a_meridian.pdf")
    R("REG-03","Cumulative A → AUTO_APPROVED",
      "PASS" if ra.get("decision")=="AUTO_APPROVED" else "FAIL")

    reset()
    rb = upload("cumulative_b_meridian.pdf")
    R("REG-04","Cumulative B → NEEDS_REVIEW",
      "PASS" if rb.get("decision")=="NEEDS_REVIEW" else "FAIL")

    # Ambiguous PO
    reset()
    rp = upload("ambiguous_po_brightwave.pdf")
    R("REG-05","Ambiguous PO → NEEDS_REVIEW",
      "PASS" if rp.get("decision")=="NEEDS_REVIEW" else "FAIL")

    # Scanned/missing
    reset()
    rs = upload("scanned_missing_number_pinnacle.pdf")
    R("REG-06","Scanned missing# → NEEDS_INFORMATION",
      "PASS" if rs.get("decision")=="NEEDS_INFORMATION" else "FAIL")


# ═══════════════════════════════════════════════
if __name__ == "__main__":
    try:
        httpx.get(B+"/api/health",timeout=5)
    except Exception as e:
        print("FATAL: QA server not reachable at",B)
        sys.exit(1)

    test_scenario_a()
    test_scenario_b()
    test_scenario_c()
    test_scenario_d()
    test_regression()

    total = P+F+BL
    print("\n"+"="*60)
    print(f"RESULTS: {P} PASS, {F} FAIL, {BL} BLOCKED (total {total})")
    print("="*60)

    with open("qa/advanced_results.json","w") as f:
        json.dump({"summary":{"pass":P,"fail":F,"blocked":BL,"total":total},
                   "results":results,"ts":datetime.utcnow().isoformat()},f,indent=2,default=str)
    print("Saved to qa/advanced_results.json")
    sys.exit(1 if F>0 else 0)
