"""Numbers reconcile across every surface (v2.1 QA).

Source of truth: docs/data/kpis.json (+ policies.json). Checked surfaces:
  * site, rendered in Chromium (Simple + Expert): Mission/Results and Capital show the A4 capital table with the exact
    row texts and the verbatim note, the verbatim scope line, and every KPI tile value (.kpi-value) traces to a number in
    kpis.json / policies.json; every .name-tag on every route reads the A3 display name of its code;
  * README.md: capital table rows, scope line, display names, headline hours (P0/P1/P2/I125 and the P2-vs-P0 delta);
  * workbook README sheet (docs/downloads + excel/ copy identical): capital table text/units/AED, scope line, plan names,
    KPI table values;
  * deck text: presentations/*.md and the .pptx text: display names, no "+AED 0.6M" without the gross lines, every
    "N h" headline hour figure is a data value.
Results: reports/audit/numbers_reconcile.json
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import audit_lib as AL  # noqa: E402
from test_interaction_audit import ROUTES, VIEW_OF  # noqa: E402

pytestmark = pytest.mark.browser
DATA = ROOT / "docs" / "data"
REPORT = ROOT / "reports" / "audit" / "numbers_reconcile.json"
KPIS = json.loads((DATA / "kpis.json").read_text())
POL = json.loads((DATA / "policies.json").read_text())
CAP = KPIS["capital_table"]
ROWS = {r["id"]: r for r in CAP["rows"]}
SCOPE = KPIS["scope_line"]
NAMES = {k: v["display_name"] for k, v in KPIS["display_names"].items()}
HEAD_CODES = ["P0", "P1", "P2", "I125"]
POLKPI = {p["policy_id"]: p.get("kpi", {}) for p in POL["policies"]}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("−", "-").replace("–", "-").replace(" ", " ")).strip()


def _record(section, payload):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        d = json.loads(REPORT.read_text())
    except Exception:  # noqa: BLE001
        d = {}
    d[section] = payload
    d["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    d["truth"] = {"capital_rows": {k: v["text"] for k, v in ROWS.items()}, "note": CAP["note"], "scope": SCOPE,
                  "names": {c: NAMES[c] for c in HEAD_CODES}, "aog_hours": {c: POLKPI.get(c, {}).get("aog_hours", {}).get("mean") for c in HEAD_CODES}}
    REPORT.write_text(json.dumps(d, indent=1, ensure_ascii=False))


def _numbers(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers(v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.add(float(obj))
    return out


TRUTH_NUMBERS = _numbers(KPIS) | _numbers(POL)
# derived values the UI legitimately shows: deltas between headline plans, percentage-point gaps
for a in HEAD_CODES:
    for b in HEAD_CODES:
        for k in ("aog_hours", "spare_capital_aed", "total_annual_cost_aed", "aog_events", "immediate_fill_rate"):
            va, vb = POLKPI.get(a, {}).get(k, {}).get("mean"), POLKPI.get(b, {}).get(k, {}).get("mean")
            if va is not None and vb is not None:
                TRUTH_NUMBERS.add(float(va - vb))
                if vb:
                    TRUTH_NUMBERS.add(float((va - vb) / vb))


WIDE_NUMBERS = set(TRUTH_NUMBERS)
for _f in ("method", "frontier", "aog_lab", "network", "rotables"):
    try:
        WIDE_NUMBERS |= _numbers(json.loads((DATA / f"{_f}.json").read_text()))
    except Exception:  # noqa: BLE001
        pass


def traces(shown: str, pool=None) -> bool:
    """Does a displayed number string (e.g. '1,480', '97.7', '49.0', '0.6') match some data value in a common format?"""
    t = norm(shown).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return True
    x = float(m.group(0))
    dp = len(m.group(0).split(".")[1]) if "." in m.group(0) else 0
    tol = 0.5 * 10 ** (-dp) + 1e-9
    for v in (TRUTH_NUMBERS if pool is None else pool):
        for scale in (1, 100, 1e-6, 1e-3, 1e-9):
            for s in (v * scale, -v * scale):
                if abs(s - x) <= tol:
                    return True
    return False


# --------------------------------------------------------------------------------------------- site


@pytest.fixture(scope="module")
def site_scan():
    sync = pytest.importorskip("playwright.sync_api")
    out = {}
    with AL.serve_docs() as base, sync.sync_playwright() as pw:
        b = pw.chromium.launch()
        for mode in ("simple", "expert"):
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', '{mode}'); }} catch (e) {{}}")
            page = ctx.new_page()
            for route in ROUTES + ["mission?section=results"]:
                page.goto("about:blank")
                page.goto(base + f"#/{route}")
                page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=20000)
                page.wait_for_timeout(1200)                         # let count-ups finish (600 ms)
                out[f"{route}:{mode}"] = page.evaluate("""() => {
                  const T = (e) => (e?.innerText || e?.textContent || '').replace(/\\s+/g, ' ').trim();
                  return {
                    capital: [...document.querySelectorAll('#view [data-role=capital-table]')].map((f) => ({
                      buy: T(f.querySelector('tr[data-row=buy]')), shed: T(f.querySelector('tr[data-row=shed]')),
                      net: T(f.querySelector('tr[data-row=net]')), note: T(f.querySelector('.capital-note')), all: T(f) })),
                    scope: [...document.querySelectorAll('#view [data-role=scope]')].map(T),
                    kpis: [...document.querySelectorAll('#view .kpi-value')].map((v) => ({ value: T(v),
                      label: T(v.closest('.kpi, .card, [class*=kpi]')?.querySelector('.kpi-label')) })),
                    names: [...document.querySelectorAll('#view .name-tag[data-code]')].map((n) => ({ code: n.dataset.code,
                      text: T(n.cloneNode(true).querySelector('.mono-tag') ? (() => { const c = n.cloneNode(true); c.querySelector('.mono-tag')?.remove(); return c; })() : n) })),
                    netAlone: /Net change in average simulated spare inventory/.test(T(document.querySelector('#view'))) &&
                      ![...document.querySelectorAll('#view [data-role=capital-table]')].length,
                  }; }""")
            ctx.close()
        b.close()
    return out


def _row_ok(shown: str, row) -> bool:
    return norm(row["text"]) in norm(shown) and norm(row["label"]) in norm(shown)


@pytest.mark.parametrize("surface", ["mission?section=results", "capital"])
def test_capital_table_on_site(site_scan, surface):
    problems = []
    for mode in ("simple", "expert"):
        s = site_scan[f"{surface}:{mode}"]
        if not s["capital"]:
            problems.append(f"{surface} ({mode}): no [data-role=capital-table]")
            continue
        for i, c in enumerate(s["capital"]):
            for key, rid in (("buy", "bought"), ("shed", "removed"), ("net", "net_inventory")):
                if not _row_ok(c[key], ROWS[rid]):
                    problems.append(f"{surface} ({mode}) table {i} row {key}: shows {c[key]!r}, expected {ROWS[rid]['label']!r} + {ROWS[rid]['text']!r}")
            if norm(CAP["note"]) not in norm(c["note"] or c["all"]):
                problems.append(f"{surface} ({mode}) table {i}: note differs: {c['note']!r}")
        if not any(norm(x) == norm(SCOPE) for x in s["scope"]):
            problems.append(f"{surface} ({mode}): verbatim scope line missing (found {s['scope'][:3]})")
    _record(f"site_capital_{surface}", problems)
    assert not problems, f"[{VIEW_OF.get(surface.split('?')[0])}]\n" + "\n".join(problems)


def test_site_kpis_trace_to_data(site_scan):
    problems, rows = [], []
    for key, s in site_scan.items():
        route = key.split(":")[0].split("?")[0]
        if route not in ("mission", "capital"):
            continue
        for k in s["kpis"]:
            ok = traces(k["value"])
            rows.append({"page": key, **k, "ok": ok})
            if not ok:
                problems.append(f"{key} [{VIEW_OF.get(route)}]: KPI {k['label']!r} shows {k['value']!r}, not traceable to kpis.json/policies.json")
        if s["netAlone"]:
            problems.append(f"{key}: 'Net change in average simulated spare inventory' shown outside a capital table")
    _record("site_kpis", {"rows": rows, "problems": problems})
    assert rows, "no KPI tiles found on Mission/Capital"
    assert not problems, "\n".join(problems)


def test_site_display_names(site_scan):
    problems, seen = [], 0
    for key, s in site_scan.items():
        route = key.split(":")[0].split("?")[0]
        for n in s["names"]:
            seen += 1
            want = NAMES.get(n["code"])
            short = KPIS["display_names"].get(n["code"], {}).get("short_name")
            if want and norm(n["text"]) not in (norm(want), norm(short or "")):
                problems.append(f"{key} [{VIEW_OF.get(route)}]: name-tag {n['code']} reads {n['text']!r}, expected {want!r}")
    _record("site_names", {"seen": seen, "problems": sorted(set(problems))})
    assert not problems, "\n".join(sorted(set(problems))[:60])


# --------------------------------------------------------------------------------------------- README / workbook / deck


def _fmt_h(v) -> str:
    return f"{round(v):,}"


def test_readme_matches_data():
    t = norm((ROOT / "README.md").read_text())
    problems = []
    for rid, row in ROWS.items():
        if not re.search(re.escape(norm(row["label"])) + r"\s*\|\s*" + re.escape(norm(row["text"])), t):
            problems.append(f"README capital row {row['label']!r} | {row['text']!r} missing/different")
    if norm(CAP["note"]) not in t:
        problems.append("README capital note missing/different")
    if norm(SCOPE) not in t:
        problems.append("README scope line missing")
    for c in HEAD_CODES:
        if NAMES[c] not in (ROOT / "README.md").read_text():
            problems.append(f"README lacks display name {NAMES[c]!r}")
        h = POLKPI.get(c, {}).get("aog_hours", {}).get("mean")
        if h is not None and f"{_fmt_h(h)} h" not in t:
            problems.append(f"README lacks {c} hours {_fmt_h(h)} h")
    d = next(k for k in KPIS["kpis"] if k["id"] == "aog_hours")["delta"]
    if _fmt_h(abs(d)) not in t:
        problems.append(f"README lacks the P2-vs-P0 delta {_fmt_h(abs(d))}")
    # every "N h" figure in the results section is a data value
    stray = sorted({m for m in re.findall(r"(\d[\d,]*(?:\.\d+)?) h\b", t) if not traces(m, WIDE_NUMBERS)})
    _record("readme", {"problems": problems, "warnings_untraced_hour_figures": stray})
    assert not problems, "\n".join(problems)


def _wb_readme_rows(path: Path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    return [[c for c in r if c is not None] for r in wb["README"].iter_rows(values_only=True)]


def test_workbook_readme_matches_data():
    p1, p2 = ROOT / "docs/downloads/grounded_no_more_planner_workbook.xlsx", ROOT / "excel/grounded_no_more_planner_workbook.xlsx"
    problems = []
    if p2.exists() and p1.read_bytes() != p2.read_bytes():
        problems.append("docs/downloads and excel/ workbooks differ")
    rows = _wb_readme_rows(p1)
    flat = norm(" ".join(str(c) for r in rows for c in r))
    for rid, row in ROWS.items():
        r = next((r for r in rows if r and norm(str(r[0])) == norm(row["label"])), None)
        if not r:
            problems.append(f"workbook README: no row {row['label']!r}")
            continue
        if norm(str(r[1])) != norm(row["text"]):
            problems.append(f"workbook README {row['label']!r}: text {r[1]!r} != {row['text']!r}")
        nums = [x for x in r[2:] if isinstance(x, (int, float))]
        want = [x for x in (row["units"], row["aed"]) if x is not None]
        if nums[: len(want)] != want:
            problems.append(f"workbook README {row['label']!r}: numbers {nums} != {want}")
    if norm(CAP["note"]) not in flat:
        problems.append("workbook README: capital note missing")
    if norm(SCOPE) not in flat:
        problems.append("workbook README: scope line missing")
    for c in HEAD_CODES:
        if norm(NAMES[c]) not in flat:
            problems.append(f"workbook README lacks {NAMES[c]!r}")
    # KPI table: label, note, P0, P2, I125
    kmap = {"Immediate fill rate": "immediate_fill_rate", "Spare capital": "spare_capital_aed", "Total annual cost": "total_annual_cost_aed",
            "AOG events / year": "aog_events", "Expected material-related downtime h / year": "aog_hours"}
    for r in rows:
        if r and r[0] in kmap and len(r) >= 5:
            k = kmap[r[0]]
            want = [POLKPI.get(c, {}).get(k, {}).get("mean") for c in ("P0", "P2", "I125")]
            got = [x for x in r if isinstance(x, (int, float))][:3]
            if any(w is not None and abs(g - w) > 1e-6 * max(1, abs(w)) for g, w in zip(got, want)):
                problems.append(f"workbook README KPI {r[0]!r}: {got} != data {want}")
    exported = next((str(r[1]) for r in rows if r and r[0] == "Site data"), "")
    _record("workbook", {"problems": problems, "site_data_line": exported, "kpis_meta": KPIS["meta"].get("generated_at"),
                         "kpis_git": KPIS["meta"].get("git_sha")})
    assert not problems, "\n".join(problems)


def _deck_texts() -> dict:
    out = {str(p.relative_to(ROOT)): p.read_text(errors="ignore") for p in sorted((ROOT / "presentations").glob("*.md"))}
    for pp in sorted((ROOT / "presentations").glob("*.pptx")):
        try:
            from pptx import Presentation
            prs = Presentation(str(pp))
            out[str(pp.relative_to(ROOT))] = "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
        except Exception as exc:  # noqa: BLE001
            out[str(pp.relative_to(ROOT))] = f"__ERROR__ {exc}"
    return out


def test_deck_text_matches_data():
    problems, warnings = [], []
    texts = _deck_texts()
    assert texts, "no deck text (presentations/*.md / *.pptx)"
    for name, raw in texts.items():
        if raw.startswith("__ERROR__"):
            problems.append(f"{name}: cannot read: {raw}")
            continue
        t = norm(raw)
        if re.search(r"\+?AED 0\.6M", t) and not (norm(ROWS["bought"]["text"]) in t and "3.1M" in t):
            problems.append(f"{name}: '+AED 0.6M' shown without the gross bought/removed lines (A4)")
        for code in HEAD_CODES:
            short = KPIS["display_names"][code]["short_name"]
            if re.search(rf"\b{code}\b", raw) and short not in raw:
                problems.append(f"{name}: uses code {code} without its display name")
        stray = sorted({m for m in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s?h\b", t) if not traces(m, WIDE_NUMBERS)})
        if stray:
            warnings.append(f"{name}: hour figures not found in docs/data (check by hand): {stray[:12]}")
        if name.endswith(".pptx") and norm(SCOPE) not in t:
            problems.append(f"{name}: verbatim scope line missing")
    _record("deck", {"files": list(texts), "problems": problems, "warnings": warnings})
    assert not problems, "\n".join(problems)
