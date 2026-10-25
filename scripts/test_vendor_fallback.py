import httpx, time
B = "http://127.0.0.1:8000"
httpx.post(B+"/api/demo/reset", timeout=20); time.sleep(0.5)

# Upload happy path — Apex is a known vendor
with open("data/fixtures/happy_path_apex_invoice.pdf","rb") as f:
    httpx.post(B+"/api/upload", files={"file":("hp.pdf",f,"application/pdf")}, timeout=30)

# Upload scanned — Pinnacle is a known vendor but no invoice#
with open("data/fixtures/scanned_missing_number_pinnacle.pdf","rb") as f:
    httpx.post(B+"/api/upload", files={"file":("scan.pdf",f,"application/pdf")}, timeout=30)

cases = httpx.get(B+"/api/cases", timeout=10).json()
print("Cases in table:")
for c in cases:
    print(f"  vendor={c['vendor_name']}  decision={c['decision']}  invoice={c['invoice_number']}")

# Check: known vendor should show resolved name, unknown should show extracted name
print("\nPASS" if all(c["vendor_name"] is not None for c in cases) else "FAIL: some vendors still show None")
