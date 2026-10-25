"""Capture Zamp.ai brand reference colors and before screenshots."""
from playwright.sync_api import sync_playwright
import json, time
from pathlib import Path

OUT = Path("qa/evidence/ui_redesign")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # Zamp.ai inspection
    print("Fetching zamp.ai...")
    page.goto("https://www.zamp.ai/", wait_until="networkidle", timeout=25000)
    time.sleep(3)
    page.screenshot(path=str(OUT / "zamp_homepage.png"), full_page=False)

    colors = page.evaluate("""() => {
        const r = {};
        const body = document.body;
        const bcs = getComputedStyle(body);
        r.body_bg = bcs.backgroundColor;
        r.body_color = bcs.color;
        r.body_font = bcs.fontFamily;

        // All unique background colors from elements
        const bgs = new Set();
        const fgs = new Set();
        document.querySelectorAll('*').forEach(el => {
            const s = getComputedStyle(el);
            if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent') {
                bgs.add(s.backgroundColor);
            }
            fgs.add(s.color);
        });
        r.unique_backgrounds = [...bgs].slice(0, 20);
        r.unique_foregrounds = [...fgs].slice(0, 20);

        // First prominent button
        document.querySelectorAll('a, button').forEach(b => {
            const s = getComputedStyle(b);
            if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)' && !r.btn_bg) {
                r.btn_bg = s.backgroundColor;
                r.btn_color = s.color;
                r.btn_radius = s.borderRadius;
                r.btn_padding = s.padding;
                r.btn_font_weight = s.fontWeight;
            }
        });

        // Headings
        const h = document.querySelector('h1');
        if (h) {
            const hs = getComputedStyle(h);
            r.h1_color = hs.color;
            r.h1_font = hs.fontFamily;
            r.h1_weight = hs.fontWeight;
            r.h1_size = hs.fontSize;
        }

        // Nav/header
        const nav = document.querySelector('nav') || document.querySelector('header');
        if (nav) {
            const ns = getComputedStyle(nav);
            r.nav_bg = ns.backgroundColor;
            r.nav_color = ns.color;
        }

        return r;
    }""")

    print("Brand reference captured:")
    for k, v in colors.items():
        if isinstance(v, list):
            print(f"  {k}: {v[:8]}...")
        else:
            print(f"  {k}: {v}")

    with open(str(OUT / "zamp_brand_colors.json"), "w") as f:
        json.dump(colors, f, indent=2)

    # Before screenshots of current app
    print("\nCapturing before screenshots...")
    page.set_viewport_size({"width": 1366, "height": 768})

    page.goto("http://127.0.0.1:8111/", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "before_dashboard.png"))

    page.goto("http://127.0.0.1:8111/health-page", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "before_health.png"))

    browser.close()
    print("Done")
