"""Keyboard audit (v2.1 QA): Tab order, Enter/Space activation, Esc closes overlays, focus never lost to <body>.

Per route (Chromium, 1440 px, Simple mode):
  1. Tab walk from the top of the document: every visible, enabled, tabbable control must be reached (no unreachable
     controls); the walk must cycle back to the start (no focus trap); no positive tabindex (illogical order). DOM-order
     inversions and big upward jumps inside the view are reported as warnings.
  2. Enter (all controls) and Space (buttons / tabs / radios / checkboxes / summary) must produce a visible effect
     within 1 s (same effect rules as audit_lib).
  3. Every control whose activation opened a modal / drawer / tour / tooltip: Esc closes it and focus is not left on
     <body> (it should return to the invoker; "returned to invoker" is recorded).
  4. Shell: "?" help modal, the 60-second tour and (at 390 px) the navigation rail close on Esc with focus restored.
Results: reports/audit/keyboard/<route>.json (+ keyboard_summary.json)
WebKit is not used for the Tab walk: macOS WebKit skips links on Tab unless the OS setting is on.
"""
from __future__ import annotations

import json
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
OUT = ROOT / "reports" / "audit" / "keyboard"
MAX_ACTIVATE = 24          # controls per route exercised with Enter/Space (spread evenly over the tab order)

TABBABLE_JS = r"""() => {
  const SEL = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex], [contenteditable=true], audio[controls], video[controls]';
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  document.querySelectorAll('[data-kbd]').forEach((e) => e.removeAttribute('data-kbd')); window.__kbdU = 0;
  let n = 0; const out = [];
  document.querySelectorAll(SEL).forEach((e) => {
    const ti = e.getAttribute('tabindex');
    if (ti !== null && +ti < 0) return;
    if (e.disabled || e.closest('[inert], [hidden]') || (e.closest('details:not([open])') && e.tagName !== 'SUMMARY' && !e.closest('summary'))) return;
    // a summary nested in a CLOSED outer <details> is not rendered (Chromium keeps its layout box: content-visibility)
    if (e.closest('summary') && e.closest('summary').parentElement?.parentElement?.closest('details:not([open])')) return;
    if (e.tagName === 'SUMMARY' && e.parentElement?.tagName !== 'DETAILS') return;
    if (!vis(e) || e.closest('.sr-only') && !e.matches('.skip-link')) return;
    const id = 'k' + (n++); e.dataset.kbd = id;
    const r = e.getBoundingClientRect();
    out.push({ id, tag: e.tagName.toLowerCase(), role: e.getAttribute('role') || '', type: (e.getAttribute('type') || '').toLowerCase(),
      tabindex: ti === null ? null : +ti, label: (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 60),
      inView: !!e.closest('#view'), x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY),
      haspopup: e.getAttribute('aria-haspopup') || '', expanded: e.getAttribute('aria-expanded'),
      external: e.tagName === 'A' && /^https?:/i.test(e.getAttribute('href') || '') && !e.href.startsWith(location.origin),
      current: e.getAttribute('aria-checked') === 'true' || e.getAttribute('aria-selected') === 'true' || e.getAttribute('aria-current') === 'page' || (e.type === 'radio' && e.checked) });
  });
  return out;
}"""

ACTIVE_JS = """() => { const a = document.activeElement; if (!a || a === document.body || a === document.documentElement) return { id: 'BODY' };
  if (!a.dataset.kbd) { window.__kbdU = (window.__kbdU || 0) + 1; a.dataset.kbd = 'u' + window.__kbdU; }   // focusable not in the tabbable list (e.g. SVG points)
  return { id: a.dataset.kbd,
           label: (a.getAttribute('aria-label') || a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 50) }; }"""


@pytest.fixture(scope="module")
def site():
    with AL.serve_docs() as base:
        yield base


@pytest.fixture(scope="module")
def browser():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _ctx(browser, vp=(1440, 900), mode="simple"):
    ctx = browser.new_context(viewport={"width": vp[0], "height": vp[1]}, accept_downloads=True)
    ctx.add_init_script(f"try {{ localStorage.setItem('gnm-mode', {json.dumps(mode)}); }} catch (e) {{}}")
    page = ctx.new_page()
    errs: list[str] = []
    page.on("console", lambda m: errs.append(f"console.error: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    events: list[str] = []
    page.on("download", lambda d: events.append("download"))
    ctx.on("page", lambda p: events.append("new-tab"))
    page._kbd_events = events  # noqa: SLF001
    return ctx, page, errs


def _load(page, base, route):
    page.goto("about:blank")                     # force a real document load (a hash-only goto would not reload)
    page.goto(base + f"#/{route}")
    page.wait_for_function("document.documentElement.dataset.ready === 'true'", timeout=20000)
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0); document.activeElement && document.activeElement.blur && document.activeElement.blur()")


def tab_walk(page, expected: list[dict]) -> dict:
    """Press Tab until focus cycles back to the first reached element (or body twice)."""
    limit = len(expected) + 250
    seq, stuck, wraps = [], 0, 0
    for _ in range(limit):
        page.keyboard.press("Tab")
        a = page.evaluate(ACTIVE_JS)
        if seq and a["id"] == seq[-1]["id"] and a["id"] != "BODY":
            stuck += 1
            if stuck >= 3:
                break
        else:
            stuck = 0
        if a["id"] == "BODY":
            wraps += 1
            if wraps >= 2:
                break
        elif seq and a["id"] == next((s["id"] for s in seq if s["id"] != "BODY"), None):
            seq.append(a)
            break
        seq.append(a)
    reached = [s["id"] for s in seq if s["id"] != "BODY"]
    cycled = bool(seq) and (seq[-1]["id"] == "BODY" or (len(reached) > 1 and reached[-1] == reached[0]) or wraps >= 1)
    return {"sequence": seq, "reached": reached, "stuck": stuck >= 3, "cycled": cycled, "presses": len(seq)}


def _activate(page, base, route, d: dict, key: str) -> dict:
    loc = page.locator(f"[data-kbd='{d['id']}']")
    if loc.count() == 0:
        return {"ok": None, "note": "gone after re-render"}
    loc.focus()
    page.evaluate(AL.OBSERVE_JS)
    before = page.evaluate(AL.STATE_JS)
    page.wait_for_timeout(30)
    page.evaluate(AL.OBSERVE_JS)
    page._kbd_events.clear()  # noqa: SLF001
    page.keyboard.press(key)
    effects, ms = AL._wait_effect(page, before, 1000, page._kbd_events)  # noqa: SLF001
    effects += [e for e in page._kbd_events if e not in effects]  # noqa: SLF001
    effects = [e for e in effects if e != "focus-change"] or effects
    res = {"ok": bool(effects) and effects != ["focus-change"], "effects": effects, "ms": ms}
    st = page.evaluate(AL.STATE_JS)
    opened = [k for k in ("modal", "drawer", "story", "tooltip") if st[k] and not before[k]]
    if opened:
        page.keyboard.press("Escape")
        page.wait_for_timeout(350)
        st2 = page.evaluate(AL.STATE_JS)
        still = [k for k in opened if st2[k]]
        act = page.evaluate(ACTIVE_JS)
        res["esc"] = {"opened": opened, "closed": not still, "focus": act["id"], "returned_to_invoker": act["id"] == d["id"]}
        if still or act["id"] == "BODY":
            res["ok"] = False
            res["note"] = (f"Esc did not close {still}" if still else "") + (" focus lost to <body> after Esc" if act["id"] == "BODY" else "")
    return res


def _restore(page, base, route):
    st = page.evaluate(AL.STATE_JS)
    if st["modal"] or st["drawer"] or st["story"] or page.evaluate("location.hash").split("?")[0] != f"#/{route}" or \
            page.evaluate("!!document.querySelector('#app')?.classList.contains('rail-open')"):
        _load(page, base, route)
        page.evaluate(TABBABLE_JS)
        return True
    return False


SPACE_OK = ("button", "summary")


def audit_keyboard(browser, base, route) -> dict:
    ctx, page, errs = _ctx(browser)
    rep = {"route": route, "owner": VIEW_OF.get(route), "problems": [], "warnings": []}
    try:
        _load(page, base, route)
        expected = page.evaluate(TABBABLE_JS)
        walk = tab_walk(page, expected)
        reached = set(walk["reached"])
        exp_ids = {e["id"] for e in expected}
        unreachable = [e for e in expected if e["id"] not in reached]
        rep.update(expected=len(expected), reached=len(reached & exp_ids), presses=walk["presses"], cycled=walk["cycled"])
        for e in unreachable:
            rep["problems"].append({"type": "unreachable", "control": e["label"], "tag": e["tag"], "role": e["role"], "inView": e["inView"]})
        if walk["stuck"] or not walk["cycled"]:
            rep["problems"].append({"type": "focus-trap", "control": walk["sequence"][-1].get("label", "") if walk["sequence"] else "",
                                    "note": "focus stuck on one element" if walk["stuck"] else f"Tab never cycled back after {walk['presses']} presses"})
        extra = [s for s in walk["sequence"] if s["id"].startswith("u")]
        if extra:
            rep["warnings"].append({"type": "tab-stops-on-non-semantic-elements", "count": len({x["id"] for x in extra}), "examples": [x.get("label", "") for x in extra[:5]]})
        for e in expected:
            if e["tabindex"] and e["tabindex"] > 0:
                rep["problems"].append({"type": "positive-tabindex", "control": e["label"], "tabindex": e["tabindex"]})
        # order: DOM order inversions + big upward jumps inside the view
        pos = {e["id"]: i for i, e in enumerate(expected)}
        byid = {e["id"]: e for e in expected}
        order = [i for i in walk["reached"] if i in pos]
        inv = [(byid[a]["label"], byid[b]["label"]) for a, b in zip(order, order[1:]) if pos[b] < pos[a] and b != order[0]]
        jumps = [(byid[a]["label"], byid[b]["label"], byid[a]["y"] - byid[b]["y"]) for a, b in zip(order, order[1:])
                 if byid[a]["inView"] and byid[b]["inView"] and byid[a]["y"] - byid[b]["y"] > 400]
        if inv:
            rep["warnings"].append({"type": "dom-order-inversion", "pairs": inv[:10]})
        if jumps:
            rep["warnings"].append({"type": "upward-jump>400px", "pairs": jumps[:10]})
        # Enter / Space activation on a spread of controls
        cands = [e for e in expected if e["inView"] or e["tag"] in ("button",)]
        step = max(1, len(cands) // MAX_ACTIVATE)
        picks = cands[::step][:MAX_ACTIVATE]
        acts = []
        errs.clear()
        for d in picks:
            keys = ["Enter"]
            if d["tag"] in SPACE_OK or d["role"] in ("button", "tab", "radio", "checkbox", "switch") or d["type"] in ("checkbox", "radio"):
                keys.append(" ")
            if d["tag"] in ("input", "select", "textarea") and d["type"] not in ("checkbox", "radio"):
                continue                       # text fields / selects: Enter is not an activation
            if d["current"] and d["role"] in ("radio", "tab") or d["type"] == "radio" and d["current"]:
                continue                       # Enter/Space on the already-selected radio/tab is a correct no-op (arrows are audited by audit_lib)
            if d["role"] in ("img", "region", "group", "figure", "presentation", "none", "tooltip", "note", "article", "list", "listitem", "table", "grid") and d["tag"] not in ("button", "a"):
                continue                       # focusable for reading / scrolling / tooltip, not an action: Enter is a no-op by design
            if d.get("external"):
                continue                       # external links are checked by test_links_downloads (not followed here)
            if d["tag"] == "a" and d["role"] not in ("button", "tab"):
                keys = ["Enter"]
            for k in keys:
                try:
                    _load(page, base, route)          # fresh state per activation: ids are re-assigned deterministically
                    page.evaluate(TABBABLE_JS)
                    errs.clear()
                    r = _activate(page, base, route, d, k)
                except Exception as exc:  # noqa: BLE001
                    r = {"ok": False, "note": f"{type(exc).__name__}: {str(exc).splitlines()[0][:140]}"}
                r.update(control=d["label"], tag=d["tag"], role=d["role"], key="Space" if k == " " else k)
                if errs:
                    r["ok"], r["errors"] = False, errs[:3]
                    errs.clear()
                acts.append(r)
                if r["ok"] is False:
                    rep["problems"].append({"type": f"{r['key']}-no-effect" if "esc" not in r else "esc", "control": d["label"], "tag": d["tag"],
                                            "role": d["role"], "note": r.get("note", ""), "errors": r.get("errors", [])})
        rep["activation"] = acts
        # shell overlays: ?, tour, rail (390)
        rep["shell"] = _shell_overlays(browser, base, route)
        for s in rep["shell"]:
            if not s["ok"]:
                rep["problems"].append({"type": "shell-esc", "control": s["what"], "note": s["note"], "owner": "SHELL (docs/js/app.js)"})
    finally:
        ctx.close()
    return rep


def _shell_overlays(browser, base, route) -> list[dict]:
    out = []
    for what, vp in (("help modal (?)", (1440, 900)), ("tour (rail button)", (1440, 900)), ("nav rail (390 menu)", (390, 844))):
        ctx, page, errs = _ctx(browser, vp=vp)
        try:
            _load(page, base, route)
            page.evaluate(TABBABLE_JS)
            if what.startswith("help"):
                inv = page.locator("#view a[href]:visible, #view button:visible").first
                inv.focus()
                page.keyboard.press("?")
                sel = ".modal"
            elif what.startswith("tour"):
                page.evaluate("window.__gnmTourStepMs = 600000")
                inv = page.locator(".nav-item--btn[data-route=tour]").first
                inv.focus()
                page.keyboard.press("Enter")
                sel = ".story"
            else:
                inv = page.locator("#menu-btn")
                inv.focus()
                page.keyboard.press("Enter")
                sel = "#app.rail-open"
            inv_id = inv.get_attribute("data-kbd")
            inv_label = (inv.text_content() or inv.get_attribute("aria-label") or "").strip()[:40]
            try:
                page.wait_for_selector(sel, timeout=3000)
            except Exception:  # noqa: BLE001
                out.append({"what": what, "ok": False, "note": f"did not open via keyboard ({sel})"})
                continue
            page.wait_for_timeout(300)
            if what.startswith("nav"):
                page.keyboard.press("Tab")       # focus should move into the open rail, then Esc
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            open_ = page.locator(sel).count() > 0
            act = page.evaluate(ACTIVE_JS)
            ok = not open_ and act["id"] != "BODY"
            out.append({"what": what, "ok": ok, "invoker": inv_label, "focus_after": act, "returned_to_invoker": act["id"] == inv_id,
                        "note": ("still open after Esc; " if open_ else "") + (f"focus lost to <body> (invoker: {inv_label!r})" if act["id"] == "BODY" else "")})
        except Exception as exc:  # noqa: BLE001
            out.append({"what": what, "ok": False, "note": f"{type(exc).__name__}: {str(exc).splitlines()[0][:140]}"})
        finally:
            ctx.close()
    return out


@pytest.mark.parametrize("route", ROUTES)
def test_keyboard(site, browser, route):
    rep = audit_keyboard(browser, site, route)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{route}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    summary = {}
    for f in sorted(OUT.glob("*.json")):
        if f.name.startswith("_"):
            continue
        r = json.loads(f.read_text())
        summary[r["route"]] = {"owner": r["owner"], "expected": r.get("expected"), "reached": r.get("reached"), "cycled": r.get("cycled"),
                               "problems": r["problems"], "warnings": [w["type"] for w in r["warnings"]]}
    (OUT / "_summary.json").write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "routes": summary}, indent=1, ensure_ascii=False))
    assert not rep["problems"], f"{route}: " + "\n".join(json.dumps(p, ensure_ascii=False) for p in rep["problems"][:40])
