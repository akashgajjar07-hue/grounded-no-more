"""Playwright smoke test against the LIVE GitHub Pages URL: every route at both viewports.
Fails on console errors, failed requests, visible NaN/undefined/null, or fixture chips."""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://akashgajjar07-hue.github.io/grounded-no-more/"
ROUTES = ["mission", "parts", "parts?ata=32&pn=GN-32-R014", "forecast", "rotables?pn=GN-32-R014", "network?station=BOM", "about",
          "capital", "aog?incident=AOG-0001", "actions", "method"]
bad = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for vw in [(1440, 900), (390, 844)]:
        pg = b.new_page(viewport={"width": vw[0], "height": vw[1]})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("requestfailed", lambda r: errs.append("FAILED " + r.url))
        for r in ROUTES:
            errs.clear()
            pg.goto(BASE + "#/" + r, wait_until="networkidle")
            pg.wait_for_timeout(2500)
            txt = pg.inner_text("main") if pg.query_selector("main") else pg.inner_text("body")
            words = [w for w in ("NaN", "undefined", "null") if f" {w} " in f" {txt} "]
            fx = pg.query_selector(".chip-fixture")
            status = "ok" if not (errs or words or fx) else f"ERR {errs[:2]} {words} fixture={bool(fx)}"
            if status != "ok":
                bad.append((vw, r, status))
            print(f"{vw[0]:>4} {r:32s} {status}")
            if r == "mission":
                pg.screenshot(path=f"docs/design-review/live-mission-{vw[0]}.png")
        pg.close()
    b.close()
print("FAILURES", len(bad))
sys.exit(1 if bad else 0)
