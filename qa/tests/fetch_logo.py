"""Fetch Zamp logo from official website and save locally."""
from playwright.sync_api import sync_playwright
import time, json
from pathlib import Path

OUT = Path("app/static")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.zamp.ai/", wait_until="networkidle", timeout=25000)
    time.sleep(3)

    # Extract ALL SVGs from the nav area and first link
    data = page.evaluate("""() => {
        const r = {svgs: [], imgs: []};
        // Get all SVGs
        document.querySelectorAll('svg').forEach((svg, i) => {
            if (i < 5) {
                r.svgs.push({
                    index: i,
                    html: svg.outerHTML,
                    parent_tag: svg.parentElement?.tagName,
                    parent_href: svg.closest('a')?.href || null,
                    viewBox: svg.getAttribute('viewBox'),
                    width: svg.getAttribute('width'),
                    height: svg.getAttribute('height')
                });
            }
        });
        // Get all images in the nav
        const nav = document.querySelector('nav') || document.querySelector('header');
        if (nav) {
            nav.querySelectorAll('img').forEach(img => {
                r.imgs.push({src: img.src, alt: img.alt, w: img.naturalWidth, h: img.naturalHeight});
            });
            // Also get the full innerHTML of first link
            const firstLink = nav.querySelector('a');
            if (firstLink) {
                r.first_link_html = firstLink.innerHTML.substring(0, 2000);
                r.first_link_href = firstLink.href;
            }
        }
        return r;
    }""")

    print("First SVGs found:")
    for svg in data.get("svgs", []):
        print(f"  SVG #{svg['index']}: parent={svg['parent_tag']}, href={svg.get('parent_href','')}, viewBox={svg.get('viewBox','')}")
        if svg.get("parent_href") and "zamp" in (svg.get("parent_href") or ""):
            print("    *** This is likely the logo ***")
            # Save it
            html = svg["html"]
            with open(OUT / "zamp-logo.svg", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"    Saved to {OUT / 'zamp-logo.svg'} ({len(html)} bytes)")

    print("\nImages in nav:")
    for img in data.get("imgs", []):
        print(f"  img: {img['src'][:80]} alt={img['alt']} {img['w']}x{img['h']}")

    print("\nFirst link HTML (truncated):")
    print(data.get("first_link_html", "NOT FOUND")[:500])

    # Also extract the brand gradient from the site
    gradient = page.evaluate("""() => {
        const els = document.querySelectorAll('*');
        for (const el of els) {
            const bg = getComputedStyle(el).backgroundImage;
            if (bg && bg.includes('gradient')) {
                return {element: el.tagName + '.' + el.className, gradient: bg.substring(0, 300)};
            }
        }
        return null;
    }""")
    if gradient:
        print("\nFirst gradient found:", gradient)
    else:
        print("\nNo CSS gradients found on the page")

    browser.close()
