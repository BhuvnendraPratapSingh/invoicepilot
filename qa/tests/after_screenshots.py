"""Capture after-redesign screenshots for visual verification."""
from playwright.sync_api import sync_playwright
import httpx, time, json
from pathlib import Path

BASE = "http://127.0.0.1:8111"
OUT = Path("qa/evidence/ui_redesign")
OUT.mkdir(parents=True, exist_ok=True)

# Reset to baseline + upload fixtures to populate dashboard
httpx.post(BASE + "/api/demo/reset", timeout=30)
time.sleep(0.5)

# Upload happy path to have data
with open("data/fixtures/happy_path_apex_invoice.pdf", "rb") as f:
    httpx.post(BASE + "/api/upload", files={"file": ("happy_path.pdf", f, "application/pdf")}, timeout=30)

# Upload cumulative B for review case
with open("data/fixtures/cumulative_b_meridian.pdf", "rb") as f:
    httpx.post(BASE + "/api/upload", files={"file": ("cumulative_b.pdf", f, "application/pdf")}, timeout=30)

# Upload ambiguous PO
with open("data/fixtures/ambiguous_po_brightwave.pdf", "rb") as f:
    r_amb = httpx.post(BASE + "/api/upload", files={"file": ("ambiguous.pdf", f, "application/pdf")}, timeout=30).json()

# Get case IDs
cases = httpx.get(BASE + "/api/cases", timeout=10).json()

print(f"Populated {len(cases)} cases for screenshots")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # Desktop viewport
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # Dashboard with data
    page.goto(BASE + "/", wait_until="networkidle", timeout=15000)
    time.sleep(2)
    page.screenshot(path=str(OUT / "after_dashboard.png"))
    print("Captured: after_dashboard.png")

    # Case detail - approved
    approved = [c for c in cases if c.get("decision") == "AUTO_APPROVED"]
    if approved:
        page.goto(BASE + "/case/" + approved[0]["id"], wait_until="networkidle", timeout=15000)
        time.sleep(2)
        page.screenshot(path=str(OUT / "after_case_approved.png"))
        print("Captured: after_case_approved.png")

    # Case detail - needs review
    review = [c for c in cases if c.get("decision") == "NEEDS_REVIEW"]
    if review:
        page.goto(BASE + "/case/" + review[0]["id"], wait_until="networkidle", timeout=15000)
        time.sleep(2)
        page.screenshot(path=str(OUT / "after_case_review.png"))
        print("Captured: after_case_review.png")

    # Health page
    page.goto(BASE + "/health-page", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "after_health.png"))
    print("Captured: after_health.png")

    # Empty dashboard
    httpx.post(BASE + "/api/demo/reset", timeout=30)
    time.sleep(0.5)
    page.goto(BASE + "/", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "after_dashboard_empty.png"))
    print("Captured: after_dashboard_empty.png")

    # Narrow viewport
    page2 = browser.new_page(viewport={"width": 390, "height": 844})
    # Repopulate
    with open("data/fixtures/happy_path_apex_invoice.pdf", "rb") as f:
        httpx.post(BASE + "/api/upload", files={"file": ("hp.pdf", f, "application/pdf")}, timeout=30)
    page2.goto(BASE + "/", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    page2.screenshot(path=str(OUT / "after_mobile.png"))
    print("Captured: after_mobile.png")

    browser.close()
    print("\nAll after screenshots captured in", OUT)
