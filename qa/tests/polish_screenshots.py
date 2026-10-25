"""Capture polished UI screenshots at multiple viewports."""
from playwright.sync_api import sync_playwright
import httpx, time
from pathlib import Path

BASE = "http://127.0.0.1:8111"
OUT = Path("qa/evidence/ui_redesign")
OUT.mkdir(parents=True, exist_ok=True)

# Populate data
httpx.post(BASE+"/api/demo/reset", timeout=30); time.sleep(0.5)
with open("data/fixtures/happy_path_apex_invoice.pdf","rb") as f:
    httpx.post(BASE+"/api/upload", files={"file":("hp.pdf",f,"application/pdf")}, timeout=30)
with open("data/fixtures/cumulative_b_meridian.pdf","rb") as f:
    httpx.post(BASE+"/api/upload", files={"file":("cb.pdf",f,"application/pdf")}, timeout=30)
with open("data/fixtures/ambiguous_po_brightwave.pdf","rb") as f:
    r_amb = httpx.post(BASE+"/api/upload", files={"file":("amb.pdf",f,"application/pdf")}, timeout=30).json()
with open("data/fixtures/scanned_missing_number_pinnacle.pdf","rb") as f:
    r_scn = httpx.post(BASE+"/api/upload", files={"file":("scn.pdf",f,"application/pdf")}, timeout=30).json()

cases = httpx.get(BASE+"/api/cases", timeout=10).json()
print(f"Populated {len(cases)} cases")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for vp_name, w, h in [("1440", 1440, 900), ("1366", 1366, 768), ("390", 390, 844)]:
        page = browser.new_page(viewport={"width": w, "height": h})
        prefix = f"polish_{vp_name}"

        # Dashboard
        page.goto(BASE+"/", wait_until="networkidle", timeout=15000); time.sleep(1.5)
        page.screenshot(path=str(OUT/f"{prefix}_dashboard.png"))

        # Approved case
        approved = [c for c in cases if c.get("decision")=="AUTO_APPROVED"]
        if approved:
            page.goto(BASE+"/case/"+approved[0]["id"], wait_until="networkidle", timeout=15000); time.sleep(1.5)
            page.screenshot(path=str(OUT/f"{prefix}_approved.png"))

        # Review case
        review = [c for c in cases if c.get("decision")=="NEEDS_REVIEW"]
        if review:
            page.goto(BASE+"/case/"+review[0]["id"], wait_until="networkidle", timeout=15000); time.sleep(1.5)
            page.screenshot(path=str(OUT/f"{prefix}_review.png"))

        # Health
        page.goto(BASE+"/health-page", wait_until="networkidle", timeout=15000); time.sleep(1)
        page.screenshot(path=str(OUT/f"{prefix}_health.png"))

        # Empty dashboard
        if vp_name == "1440":
            httpx.post(BASE+"/api/demo/reset", timeout=30); time.sleep(0.5)
            page.goto(BASE+"/", wait_until="networkidle", timeout=15000); time.sleep(1)
            page.screenshot(path=str(OUT/f"{prefix}_empty.png"))
            # Re-populate for next viewport
            with open("data/fixtures/happy_path_apex_invoice.pdf","rb") as f:
                httpx.post(BASE+"/api/upload", files={"file":("hp.pdf",f,"application/pdf")}, timeout=30)
            with open("data/fixtures/cumulative_b_meridian.pdf","rb") as f:
                httpx.post(BASE+"/api/upload", files={"file":("cb.pdf",f,"application/pdf")}, timeout=30)
            cases = httpx.get(BASE+"/api/cases", timeout=10).json()

        page.close()
        print(f"  {vp_name}: captured")

    browser.close()
print("Done")
