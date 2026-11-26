#!/usr/bin/env python3
"""Visual check for the GROUNDED NO MORE web app (docs/).

Serves docs/ on a local http server, opens it in Playwright Chromium and captures the
components gallery plus every route at 1440x900 and 390x844 into
docs/design-review/<prefix>-<name>-<viewport>-v<N>.png. Console errors and failed requests
are printed and make the script exit non-zero.

Usage:
  .venv/bin/python scripts/screenshot.py                 # all pages, version 1
  .venv/bin/python scripts/screenshot.py --version 2 --only mission gallery
  .venv/bin/python scripts/screenshot.py --og            # also render docs/assets/og-image.png
  .venv/bin/python scripts/screenshot.py --contrast      # print + save WCAG contrast table only
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "design-review"

PAGES = {
    "gallery": "design/gallery.html",
    "aircraft": "assets/svg/blueprint-aircraft-top.svg",
    "mission": "index.html#/mission",
    "parts": "index.html#/parts?ata=32",
    "forecast": "index.html#/forecast",
    "rotables": "index.html#/rotables",
    "network": "index.html#/network",
    "capital": "index.html#/capital",
    "aog": "index.html#/aog",
    "actions": "index.html#/actions",
    "method": "index.html#/method",
}
VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}


# ----------------------------------------------------------------------------- contrast
def _lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _blend(fg: str, alpha: float, bg: str) -> str:
    a = [int(fg.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x * alpha + y * (1 - alpha)):02X}" for x, y in zip(a, b))


def ratio(fg: str, bg: str) -> float:
    lo, hi = sorted([_lum(fg), _lum(bg)])
    return round((hi + 0.05) / (lo + 0.05), 2)


def contrast_report() -> list[dict]:
    t = json.loads((DOCS / "design" / "tokens.json").read_text())["color"]
    faint = "#8A9BAD"  # derived --c-text-faint
    bgs = {"midnight": t["midnight"], "card": t["card"], "deep_steel": t["deep_steel"]}
    texts = {"ice (text)": t["ice"], "titanium (muted)": t["titanium"], "text-faint (derived)": faint,
             "aero_teal": t["aero_teal"], "amber": t["amber"], "red": t["red"], "copper": t["copper"],
             "slate (non-text only)": t["slate"]}
    rows = []
    for tn, tc in texts.items():
        for bn, bc in bgs.items():
            r = ratio(tc, bc)
            need = 3.0 if "non-text" in tn else 4.5
            rows.append({"fg": tn, "bg": bn, "ratio": r, "required": need, "pass": r >= need})
    # chips: text colour on its own 10-12% tint over card
    for name, key, a in [("chip REAL", "aero_teal", 0.10), ("chip DERIVED", "titanium", 0.10), ("chip ASSUMED", "amber", 0.10),
                         ("chip SIMULATED", "copper", 0.10), ("pill urgent", "red", 0.12), ("pill review", "amber", 0.12)]:
        bg = _blend(t[key], a, t["card"])
        r = ratio(t[key], bg)
        rows.append({"fg": name, "bg": f"{key} {int(a*100)}% tint on card", "ratio": r, "required": 4.5, "pass": r >= 4.5})
    rows.append({"fg": "midnight on aero_teal (primary button)", "bg": "aero_teal", "ratio": ratio(t["midnight"], t["aero_teal"]), "required": 4.5,
                 "pass": ratio(t["midnight"], t["aero_teal"]) >= 4.5})
    return rows


# ----------------------------------------------------------------------------- server
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


def serve() -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(_Quiet, directory=str(DOCS))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--prefix", default="ds")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--viewports", nargs="*", default=list(VIEWPORTS))
    ap.add_argument("--og", action="store_true")
    ap.add_argument("--contrast", action="store_true")
    ap.add_argument("--full", action="store_true", help="full-page screenshots")
    args = ap.parse_args()

    if args.contrast:
        rows = contrast_report()
        for r in rows:
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['ratio']:>5}:1  (≥{r['required']})  {r['fg']}  on  {r['bg']}")
        (DOCS / "design" / "contrast.json").write_text(json.dumps(rows, indent=1) + "\n")
        return 0 if all(r["pass"] for r in rows) else 1

    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    httpd, port = serve()
    base = f"http://127.0.0.1:{port}/"
    problems: list[str] = []
    pages = {k: v for k, v in PAGES.items() if not args.only or k in args.only}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp in args.viewports:
            w, h = VIEWPORTS[vp]
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, reduced_motion="reduce")
            for name, url in pages.items():
                page = ctx.new_page()
                page.on("console", lambda m, n=name: problems.append(f"[{n}@{vp}] console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
                page.on("pageerror", lambda e, n=name: problems.append(f"[{n}@{vp}] pageerror: {e}"))
                page.on("requestfailed", lambda r, n=name: problems.append(f"[{n}@{vp}] requestfailed: {r.url}"))
                page.on("response", lambda r, n=name: problems.append(f"[{n}@{vp}] HTTP {r.status}: {r.url}") if r.status >= 400 else None)
                if url.endswith(".svg"):
                    # standalone illustration: show it on midnight at the viewport width, with the app fonts
                    page.goto(base + "css/tokens.css")  # same-origin, script-free page
                    page.set_content(f"<html><head><link rel='stylesheet' href='{base}css/tokens.css'></head>"
                                     f"<body style='margin:0;background:#09131F'><img src='{base}{url}' style='width:100%;display:block'></body></html>")
                    page.wait_for_load_state("networkidle")
                else:
                    page.goto(base + url)
                    try:
                        page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=10000)
                    except Exception:
                        problems.append(f"[{name}@{vp}] did not signal ready")
                page.wait_for_timeout(900)
                path = OUT / f"{args.prefix}-{name}-{vp}-v{args.version}.png"
                page.screenshot(path=str(path), full_page=args.full or name in ("gallery", "aircraft"))
                print("saved", path.relative_to(ROOT))
                page.close()
            ctx.close()
        if args.og:
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(base + "assets/svg/og-card.svg")
            page.wait_for_timeout(500)
            page.screenshot(path=str(DOCS / "assets" / "og-image.png"))
            print("saved docs/assets/og-image.png")
        browser.close()
    httpd.shutdown()
    for pr in problems:
        print("PROBLEM", pr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
