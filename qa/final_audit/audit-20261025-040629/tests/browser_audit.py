"""
Priority 5: Playwright browser tests against QA server on port 8111.
Verifies actual DOM rendering, upload flow, navigation, and visual output.
"""
import json
import time
import httpx
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8222"
FIXTURE_DIR = Path("data/fixtures")
EVIDENCE = Path("qa/evidence")
EVIDENCE.mkdir(parents=True, exist_ok=True)

results = []
counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0}

def R(tid, name, status, detail=""):
    counts[status] = counts.get(status, 0) + 1
    results.append({"test_id": tid, "name": name, "status": status, "detail": detail,
                     "ts": datetime.utcnow().isoformat()})
    icon = {"PASS":"✓","FAIL":"✗","BLOCKED":"⊘"}.get(status,"?")
    line = f"  {icon} [{tid}] {name}: {status}"
    if detail and status != "PASS":
        line += f" — {detail}"
    print(line)

def reset():
    httpx.post(BASE + "/api/demo/reset", timeout=30)
    time.sleep(0.5)

print("=" * 60)
print("Priority 5: Playwright Browser Tests")
print("Target:", BASE)
print("=" * 60)

# Reset to baseline
reset()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()

    # Collect console errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # ── UI-01: Dashboard loads ──
    try:
        page.goto(BASE + "/", wait_until="networkidle", timeout=15000)
        title = page.title()
        has_brand = page.locator("text=InvoicePilot").first.is_visible()
        page.screenshot(path=str(EVIDENCE / "ui01_dashboard.png"))
        R("UI-01", "Dashboard page loads with brand",
          "PASS" if has_brand else "FAIL",
          detail="Title: " + title)
    except Exception as e:
        R("UI-01", "Dashboard loads", "FAIL", detail=str(e)[:100])

    # ── UI-02: Upload happy path PDF via file picker ──
    try:
        reset()
        page.goto(BASE + "/", wait_until="networkidle", timeout=15000)
        # The file input is hidden; set files programmatically
        file_input = page.locator('input[type="file"]#fileInput')
        file_input.set_input_files(str(FIXTURE_DIR / "happy_path_apex_invoice.pdf"))
        # Wait for redirect to case detail
        page.wait_for_url("**/case/**", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(1)  # Let JS render
        page.screenshot(path=str(EVIDENCE / "ui02_happy_case.png"))
        R("UI-02", "File upload navigates to case detail", "PASS")
    except Exception as e:
        R("UI-02", "File upload flow", "FAIL", detail=str(e)[:100])
        page.screenshot(path=str(EVIDENCE / "ui02_fail.png"))

    # ── UI-03: Decision badge visible ──
    try:
        badge = page.locator("#decisionBadge")
        badge_text = badge.text_content(timeout=5000) or ""
        R("UI-03", "Decision badge shows 'Auto-Approved'",
          "PASS" if "Approved" in badge_text else "FAIL",
          detail="Badge: " + badge_text)
    except Exception as e:
        R("UI-03", "Decision badge", "FAIL", detail=str(e)[:100])

    # ── UI-04: Stage timeline visible ──
    try:
        timeline = page.locator("#stageTimeline")
        timeline_text = timeline.text_content(timeout=5000) or ""
        has_stages = "Receive" in timeline_text or "Vendor" in timeline_text or "PO Matching" in timeline_text
        R("UI-04", "Stage timeline renders with real stages",
          "PASS" if has_stages else "FAIL",
          detail="Contains stage names: " + str(has_stages))
    except Exception as e:
        R("UI-04", "Stage timeline", "FAIL", detail=str(e)[:100])

    # ── UI-05: Extracted data visible ──
    try:
        ext_panel = page.locator("#extractedData")
        ext_text = ext_panel.text_content(timeout=5000) or ""
        has_fields = "INV-2026-0451" in ext_text or "Apex" in ext_text
        R("UI-05", "Extracted fields visible in UI",
          "PASS" if has_fields else "FAIL",
          detail="Has invoice# or vendor name: " + str(has_fields))
    except Exception as e:
        R("UI-05", "Extracted data", "FAIL", detail=str(e)[:100])

    # ── UI-06: Rule results visible ──
    try:
        rules_panel = page.locator("#ruleResults")
        rules_text = rules_panel.text_content(timeout=5000) or ""
        has_rules = "Required Fields" in rules_text or "Currency" in rules_text or "Vendor" in rules_text
        R("UI-06", "Rule results visible",
          "PASS" if has_rules else "FAIL",
          detail="Has rule names: " + str(has_rules))
    except Exception as e:
        R("UI-06", "Rule results", "FAIL", detail=str(e)[:100])

    # ── UI-07: PDF preview visible ──
    try:
        pdf_panel = page.locator("#pdfPreview")
        imgs = pdf_panel.locator("img")
        img_count = imgs.count()
        R("UI-07", "PDF page preview image rendered",
          "PASS" if img_count >= 1 else "FAIL",
          detail=f"{img_count} page images")
    except Exception as e:
        R("UI-07", "PDF preview", "FAIL", detail=str(e)[:100])

    # ── UI-08: Page refresh preserves result ──
    try:
        url_before = page.url
        page.reload(wait_until="networkidle", timeout=10000)
        time.sleep(1)
        badge_after = page.locator("#decisionBadge").text_content(timeout=5000) or ""
        R("UI-08", "Refresh preserves decision",
          "PASS" if "Approved" in badge_after else "FAIL",
          detail="After refresh: " + badge_after)
    except Exception as e:
        R("UI-08", "Refresh persistence", "FAIL", detail=str(e)[:100])

    # ── UI-09: Navigate back to dashboard, verify counts ──
    try:
        page.goto(BASE + "/", wait_until="networkidle", timeout=10000)
        time.sleep(1)
        metrics_text = page.locator("#metricsSection").text_content(timeout=5000) or ""
        page.screenshot(path=str(EVIDENCE / "ui09_dashboard_counts.png"))
        R("UI-09", "Dashboard shows metrics after upload",
          "PASS" if "1" in metrics_text else "FAIL",
          detail="Metrics visible")
    except Exception as e:
        R("UI-09", "Dashboard metrics", "FAIL", detail=str(e)[:100])

    # ── UI-10: Cases table has rows ──
    try:
        table = page.locator("#casesTable")
        table_text = table.text_content(timeout=5000) or ""
        has_row = "INV-2026-0451" in table_text or "Apex" in table_text
        R("UI-10", "Cases table shows uploaded invoice",
          "PASS" if has_row else "FAIL",
          detail="Has invoice data: " + str(has_row))
    except Exception as e:
        R("UI-10", "Cases table", "FAIL", detail=str(e)[:100])

    # ── UI-11: Audit export download ──
    try:
        # Navigate to a case and check audit link
        rows = page.locator("#casesTable tr")
        if rows.count() > 1:
            rows.nth(1).click()
            page.wait_for_url("**/case/**", timeout=5000)
            page.wait_for_load_state("networkidle", timeout=5000)
            time.sleep(0.5)
            audit_link = page.locator("#auditExportLink")
            href = audit_link.get_attribute("href") or ""
            R("UI-11", "Audit export link present",
              "PASS" if "/audit" in href else "FAIL",
              detail="href: " + href[:60])
        else:
            R("UI-11", "Audit export", "FAIL", detail="No case rows to click")
    except Exception as e:
        R("UI-11", "Audit export", "FAIL", detail=str(e)[:100])

    # ── UI-12: Health page ──
    try:
        page.goto(BASE + "/health-page", wait_until="networkidle", timeout=10000)
        time.sleep(1)
        health_text = page.locator("#healthChecks").text_content(timeout=5000) or ""
        has_checks = "database" in health_text.lower() or "pdf" in health_text.lower()
        page.screenshot(path=str(EVIDENCE / "ui12_health.png"))
        R("UI-12", "Health page renders checks",
          "PASS" if has_checks else "FAIL",
          detail="Has health check names: " + str(has_checks))
    except Exception as e:
        R("UI-12", "Health page", "FAIL", detail=str(e)[:100])

    # ── UI-13: Console errors ──
    significant_errors = [e for e in console_errors if "favicon" not in e.lower()]
    R("UI-13", "No significant console errors",
      "PASS" if len(significant_errors) == 0 else "FAIL",
      detail="; ".join(significant_errors[:3]) if significant_errors else "")

    # ── UI-14: Ambiguous PO review flow ──
    try:
        reset()
        page.goto(BASE + "/", wait_until="networkidle", timeout=10000)
        file_input = page.locator('input[type="file"]#fileInput')
        file_input.set_input_files(str(FIXTURE_DIR / "ambiguous_po_brightwave.pdf"))
        page.wait_for_url("**/case/**", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(1)

        # Should show PO selection panel
        po_panel = page.locator("#poSelectionPanel")
        po_visible = not po_panel.is_hidden()
        page.screenshot(path=str(EVIDENCE / "ui14_ambiguous_po.png"))

        if po_visible:
            # Fill in PO selection
            page.fill("#poIdInput", "PO-1005")
            page.fill("#poReason", "QA browser test: pipeline dev scope")
            page.click("button:has-text('Re-evaluate')")
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
            page.screenshot(path=str(EVIDENCE / "ui14_after_review.png"))
            badge = page.locator("#decisionBadge").text_content(timeout=5000) or ""
            R("UI-14", "Ambiguous PO review flow in browser",
              "PASS" if "Approved" in badge else "FAIL",
              detail="Badge after review: " + badge)
        else:
            R("UI-14", "Ambiguous PO review flow", "FAIL",
              detail="PO selection panel not visible")
    except Exception as e:
        R("UI-14", "Ambiguous PO review", "FAIL", detail=str(e)[:100])
        page.screenshot(path=str(EVIDENCE / "ui14_fail.png"))

    # ── UI-15: Demo reset via button ──
    try:
        page.goto(BASE + "/", wait_until="networkidle", timeout=10000)
        time.sleep(0.5)
        # Accept the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())
        reset_btn = page.locator("button:has-text('Reset Demo')")
        if reset_btn.is_visible():
            reset_btn.click()
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)
            page.screenshot(path=str(EVIDENCE / "ui15_after_reset.png"))
            R("UI-15", "Demo reset button works", "PASS")
        else:
            R("UI-15", "Demo reset button", "FAIL", detail="Button not visible")
    except Exception as e:
        R("UI-15", "Demo reset button", "FAIL", detail=str(e)[:100])

    browser.close()

print("\n" + "=" * 60)
total = sum(counts.values())
print(f"BROWSER RESULTS: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['BLOCKED']} BLOCKED")
print(f"Total: {total}")
print("=" * 60)

with open("qa/browser_results.json", "w") as f:
    json.dump({"summary": counts, "total": total, "results": results,
               "console_errors": console_errors if 'console_errors' in dir() else [],
               "ts": datetime.utcnow().isoformat()}, f, indent=2, default=str)
print("Saved to qa/browser_results.json")
print("Screenshots in qa/evidence/")

