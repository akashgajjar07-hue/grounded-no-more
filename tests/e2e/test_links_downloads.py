"""Routes, deep links, hard refresh, internal + external links and downloads (v2.1 QA).

GitHub Pages is simulated with a plain static file server over docs/ (audit_lib.serve_docs: no rewrites, no SPA
fallback), so hash routing must survive a reload on its own.

* test_route_and_hard_refresh   every route + deep link renders, survives page.reload() and a cold load in a new page
                                 (hash + params kept, same view, no console errors / failed requests). Chromium + WebKit.
* test_internal_links           every in-site href found on every route (Simple + Expert) resolves: #/route -> a real route
                                 (not the silent Mission fallback), #anchor -> element exists, relative file -> HTTP 200.
* test_downloads_*              workbook opens in openpyxl, deck PDF has a valid header/trailer, Action Centre CSV parses,
                                 every linked JSON parses, About download buttons deliver the same bytes as on disk.
* test_external_links (audit)   one request per unique external URL (site + README + docs/content), HEAD then GET,
                                 10 s timeout, one retry for network errors / 429 / 5xx (marked "flaky-retried").
Results: reports/audit/links_downloads.json
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import audit_lib as AL  # noqa: E402
from test_interaction_audit import ROUTES, VIEW_OF, _deep_links  # noqa: E402

pytestmark = pytest.mark.browser
DOCS = ROOT / "docs"
REPORT = ROOT / "reports" / "audit" / "links_downloads.json"
ALL_ROUTES = ROUTES + _deep_links()
DL_EXT = (".xlsx", ".pdf", ".csv", ".json", ".pptx", ".zip", ".md", ".webm")


def _record(section: str, payload) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        d = json.loads(REPORT.read_text())
    except Exception:  # noqa: BLE001
        d = {}
    d[section] = payload
    d["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    REPORT.write_text(json.dumps(d, indent=1, ensure_ascii=False))


@pytest.fixture(scope="module")
def site():
    with AL.serve_docs() as index:
        yield index.rsplit("/", 1)[0] + "/"          # http://127.0.0.1:port/  (GitHub Pages serves index.html at /)


@pytest.fixture(scope="module")
def pw():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        yield p


def _page(pw, browser="chromium", mode="simple", vp=(1440, 900)):
    b = getattr(pw, browser).launch()
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, accept_downloads=True)
    ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', {json.dumps(mode)}); }} catch (e) {{}}")
    page = ctx.new_page()
    errs: list[str] = []
    page.on("console", lambda m: errs.append(f"console.error: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: errs.append(f"requestfailed: {r.url} {r.failure}") if not r.url.startswith("blob:") else None)
    page.on("response", lambda r: errs.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    return b, ctx, page, errs


def _ready(page):
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=20000)
    page.wait_for_timeout(300)


ROUTE_STATE_JS = """() => ({ hash: location.hash, current: document.querySelector('.nav-item[aria-current=page]')?.dataset.route || null,
  text: (document.querySelector('#view')?.innerText || '').trim().length, title: document.title,
  err: !!document.querySelector('#view .error-state, #view [data-role=error], #view .view-error') })"""


def _check_route(state: dict, route: str) -> list[str]:
    rid = route.split("?")[0]
    out = []
    if state["current"] != rid:
        out.append(f"rendered route {state['current']!r}, expected {rid!r}")
    if not state["hash"].startswith(f"#/{route.split('?')[0]}"):
        out.append(f"hash became {state['hash']!r}")
    if "?" in route and state["hash"] != f"#/{route}" and not all(p in state["hash"] for p in route.split("?")[1].split("&")):
        out.append(f"deep-link params lost: {state['hash']!r} (wanted #/{route})")
    if state["text"] < 80:
        out.append(f"view nearly empty ({state['text']} chars)")
    if state["err"]:
        out.append("view shows an error state")
    return out


# --------------------------------------------------------------------------------------------- routes + reload


@pytest.mark.parametrize("browser", ["chromium", "webkit"])
def test_route_and_hard_refresh(site, pw, browser):
    b, ctx, page, errs = _page(pw, browser)
    problems, rows = [], []
    try:
        for route in ALL_ROUTES:
            url = f"{site}#/{route}"
            res = {"route": route, "owner": VIEW_OF.get(route.split("?")[0])}
            for phase in ("load", "reload", "cold"):
                errs.clear()
                try:
                    if phase == "load":
                        page.goto(url)
                    elif phase == "reload":
                        page.reload()
                    else:
                        p2 = ctx.new_page()
                        p2.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
                        p2.on("console", lambda m: errs.append(f"console.error: {m.text}") if m.type == "error" else None)
                        p2.goto(url)
                        _ready(p2)
                        st = p2.evaluate(ROUTE_STATE_JS)
                        p2.close()
                    if phase != "cold":
                        _ready(page)
                        st = page.evaluate(ROUTE_STATE_JS)
                    bad = _check_route(st, route) + errs[:3]
                except Exception as exc:  # noqa: BLE001
                    bad = [f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"]
                res[phase] = bad or "ok"
                if bad:
                    problems.append(f"{browser} {route} [{phase}] [{res['owner']}]: {'; '.join(bad)}")
            rows.append(res)
        # index served at "/" and at "/index.html" both route
        for u in (site, site + "index.html"):
            page.goto(u + "#/capital")
            _ready(page)
            if page.evaluate(ROUTE_STATE_JS)["current"] != "capital":
                problems.append(f"{browser} {u}#/capital did not route")
    finally:
        ctx.close()
        b.close()
    _record(f"routes_{browser}", {"rows": rows, "problems": problems})
    assert not problems, "\n".join(problems)


# --------------------------------------------------------------------------------------------- crawl

COLLECT_JS = """() => [...document.querySelectorAll('a[href]')].map((a) => ({ href: a.getAttribute('href'), abs: a.href,
  download: a.hasAttribute('download'), text: (a.textContent || a.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 60),
  inView: !!a.closest('#view') }))"""


@pytest.fixture(scope="module")
def crawl(site, pw):
    """All hrefs on every route (both modes) + the cutaway lab page. {href: {abs, download, pages:[...]}}."""
    links: dict = {}
    anchors_missing = []
    b, ctx, page, errs = _page(pw)
    try:
        for mode in ("simple", "expert"):
            ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', '{mode}'); }} catch (e) {{}}")
            for route in ALL_ROUTES + ["@lab/cutaway.html"]:
                url = f"{site}lab/cutaway.html" if route.startswith("@") else f"{site}#/{route}"
                page.goto(url)
                _ready(page)
                for a in page.evaluate(COLLECT_JS):
                    e = links.setdefault(a["href"], {"abs": a["abs"], "download": a["download"], "text": a["text"], "pages": []})
                    e["pages"].append(f"{route}:{mode}")
                    e["download"] = e["download"] or a["download"]
                    h = a["href"]
                    if h.startswith("#") and not h.startswith("#/") and len(h) > 1:
                        if not page.evaluate("(id) => !!document.getElementById(id)", h[1:]):
                            anchors_missing.append(f"{route}:{mode} -> {h}")
    finally:
        ctx.close()
        b.close()
    return {"links": links, "anchors_missing": sorted(set(anchors_missing))}


def _get(url: str, method="GET", timeout=10):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (static-site link check)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.status, (r.read() if method == "GET" else b""), r.geturl()


def test_internal_links(site, crawl):
    route_ids = set(ROUTES)
    problems, checked = [], []
    for href, e in sorted(crawl["links"].items()):
        if re.match(r"^(https?:|mailto:|tel:)", href) and not e["abs"].startswith(site):
            continue
        if href.startswith("#/"):
            rid = href[2:].split("?")[0]
            ok = rid in route_ids
            checked.append({"href": href, "kind": "route", "ok": ok})
            if not ok:
                problems.append(f"{href} (on {e['pages'][0]}) points at an unknown route -> silently falls back to Mission")
        elif href.startswith("#"):
            checked.append({"href": href, "kind": "anchor"})
        else:
            try:
                st, body, _ = _get(e["abs"].split("#")[0])
                ok = st == 200 and len(body) > 0
            except Exception as exc:  # noqa: BLE001
                ok, st = False, f"{type(exc).__name__}: {exc}"
            checked.append({"href": href, "kind": "file", "status": st, "ok": ok})
            if not ok:
                problems.append(f"{href} (on {e['pages'][0]}) -> {st}")
    problems += [f"in-page anchor target missing: {m}" for m in crawl["anchors_missing"]]
    _record("internal_links", {"checked": checked, "problems": problems})
    assert not problems, "\n".join(problems)


# --------------------------------------------------------------------------------------------- downloads


def _validate_bytes(name: str, data: bytes) -> str | None:
    """None if the file opens as its type, else the reason."""
    if not data:
        return "empty"
    n = name.lower().split("?")[0]
    try:
        if n.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
            if not wb.sheetnames:
                return "workbook has no sheets"
        elif n.endswith(".pdf"):
            if not data.startswith(b"%PDF-"):
                return "missing %PDF- header"
            if b"%%EOF" not in data[-2048:]:
                return "missing %%EOF trailer"
            if len(re.findall(rb"/Type\s*/Page[^s]", data)) < 1:
                return "no pages found"
        elif n.endswith(".csv"):
            rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
            if len(rows) < 2:
                return f"CSV has {len(rows)} rows"
            w = len(rows[0])
            ragged = [i for i, r in enumerate(rows) if r and len(r) != w]
            if ragged:
                return f"CSV ragged rows {ragged[:5]} (header has {w} columns)"
        elif n.endswith(".json"):
            json.loads(data)
        elif n.endswith(".pptx") or n.endswith(".zip"):
            import zipfile
            zipfile.ZipFile(io.BytesIO(data)).testzip()
    except Exception as exc:  # noqa: BLE001
        return f"does not open: {type(exc).__name__}: {exc}"
    return None


def test_downloads_on_disk_open():
    files = sorted((DOCS / "downloads").glob("*"))
    assert any(f.suffix == ".xlsx" for f in files), "no Excel workbook in docs/downloads"
    assert any(f.suffix == ".pdf" for f in files), "no deck PDF in docs/downloads"
    bad = {f.name: r for f in files if f.is_file() and (r := _validate_bytes(f.name, f.read_bytes()))}
    bad.update({f"data/{f.name}": r for f in sorted((DOCS / "data").glob("*.json")) if (r := _validate_bytes(f.name, f.read_bytes()))})
    _record("downloads_on_disk", {"files": {f.name: f.stat().st_size for f in files}, "problems": bad})
    assert not bad, bad


def test_downloads_linked_from_site_open(site, crawl):
    rows, problems = [], []
    for href, e in sorted(crawl["links"].items()):
        if not (e["download"] or href.lower().split("?")[0].endswith(DL_EXT)) or not e["abs"].startswith(site):
            continue
        try:
            st, body, _ = _get(e["abs"])
            why = None if st == 200 else f"HTTP {st}"
            why = why or _validate_bytes(href, body)
        except Exception as exc:  # noqa: BLE001
            why, body = f"{type(exc).__name__}: {exc}", b""
        rows.append({"href": href, "bytes": len(body), "pages": sorted(set(e["pages"]))[:6], "problem": why})
        if why:
            problems.append(f"{href} (on {e['pages'][0]}): {why}")
    _record("downloads_linked", {"rows": rows, "problems": problems})
    assert rows, "no download links found on the site"
    assert not problems, "\n".join(problems)


def test_download_buttons_deliver_files(site, pw, tmp_path):
    """Real clicks: About's workbook / deck buttons and the Action Centre 'Export CSV' (Blob) download."""
    b, ctx, page, errs = _page(pw)
    got, problems = {}, []
    try:
        page.goto(f"{site}#/about")
        _ready(page)
        for a in page.locator("#view a[download]").all():
            href = a.get_attribute("href") or ""
            with page.expect_download(timeout=10000) as dl:
                a.click()
            p = tmp_path / dl.value.suggested_filename
            dl.value.save_as(p)
            data = p.read_bytes()
            disk = (DOCS / href).read_bytes() if (DOCS / href).exists() else None
            why = _validate_bytes(p.name, data) or (None if disk is None or disk == data else "bytes differ from docs/" + href)
            got[href] = {"bytes": len(data), "problem": why}
            if why:
                problems.append(f"about: {href}: {why}")
        page.goto(f"{site}#/actions")
        _ready(page)
        btn = page.locator("[data-action=export-csv]").first
        if btn.count() == 0:
            problems.append("actions: no [data-action=export-csv] button")
        else:
            with page.expect_download(timeout=10000) as dl:
                btn.click()
            p = tmp_path / dl.value.suggested_filename
            dl.value.save_as(p)
            data = p.read_bytes()
            why = _validate_bytes(p.name, data)
            rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig")))) if not why else []
            got["actions:export-csv"] = {"file": p.name, "bytes": len(data), "rows": len(rows), "columns": rows[0] if rows else [], "problem": why}
            if why:
                problems.append(f"actions CSV {p.name}: {why}")
        if errs:
            problems += [f"console/network: {e}" for e in errs[:5]]
    finally:
        ctx.close()
        b.close()
    _record("download_buttons", {"files": got, "problems": problems})
    assert len(got) >= 3, got
    assert not problems, "\n".join(problems)


# --------------------------------------------------------------------------------------------- external links (network)

MD_LINK = re.compile(r"\]\((https?://[^)\s]+)\)|<(https?://[^>\s]+)>")


def _external_urls(crawl) -> dict:
    urls: dict = {}
    for href, e in crawl["links"].items():
        if re.match(r"^https?://", e["abs"]) and not e["abs"].startswith("http://127.0.0.1"):
            urls.setdefault(e["abs"].split("#")[0], set()).update(p for p in e["pages"][:3])
    for md in [ROOT / "README.md", *sorted((DOCS / "content").glob("*.md"))]:
        if md.exists():
            for m in MD_LINK.finditer(md.read_text(errors="ignore")):
                urls.setdefault((m.group(1) or m.group(2)).split("#")[0].rstrip(".,"), set()).add(str(md.relative_to(ROOT)))
    return urls


def _check_external(url: str) -> dict:
    out = {"url": url, "attempts": 0}
    for attempt in range(2):
        out["attempts"] = attempt + 1
        try:
            try:
                st, _, final = _get(url, method="HEAD")
            except urllib.error.HTTPError as he:
                if he.code in (403, 405, 400, 501):        # HEAD not allowed -> one GET instead
                    st, _, final = _get(url, method="GET")
                else:
                    raise
            out.update(status=st, final=final)
            break
        except urllib.error.HTTPError as he:
            out.update(status=he.code, error=f"HTTP {he.code}")
            if he.code not in (429, 500, 502, 503, 504):
                break
        except Exception as exc:  # noqa: BLE001
            out.update(status=None, error=f"{type(exc).__name__}: {str(exc)[:120]}")
        time.sleep(2)
    if out["attempts"] > 1:
        out["flaky_retried"] = True
    out["ok"] = out.get("status") == 200
    return out


@pytest.mark.audit
def test_external_links(crawl):
    urls = _external_urls(crawl)
    rows = []
    for u in sorted(urls):                                  # one request (plus at most one retry) per unique URL
        r = _check_external(u)
        r["found_on"] = sorted(urls[u])[:5]
        rows.append(r)
    bad = [r for r in rows if not r["ok"]]
    _record("external_links", {"checked": len(rows), "rows": rows, "failed": bad})
    assert rows, "no external links found"
    assert not bad, "\n".join(f"{r['url']} -> {r.get('status')} {r.get('error', '')} (on {r['found_on']})" for r in bad)
