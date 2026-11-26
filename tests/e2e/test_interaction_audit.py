"""Release-grade interaction audit (v2.1, QA).

Matrix: every workspace route + key deep-link states + #/glossary, #/planner, #/about + lab/cutaway.html
        x Simple / Expert x 1440 / 390 x Chromium / WebKit / Firefox.

Each cell runs `audit_lib.audit_route` (auto-discovery of every visible interactive element + the global shortcuts,
1 s visible-effect rule, console errors / unhandled rejections / failed requests = FAIL) and then an OVERLAY phase
that audits controls that only exist once an overlay is open (help modal from "?", the guided tour from "S").

Per-cell JSON: test-results/audit_cells/<browser>/<cell>.json (gitignored). Aggregate: reports/audit/_summary.json (rebuilt after
every cell, so a partial run still leaves a coherent summary).

Run (excluded from the default run):
    pytest -m audit tests/e2e/test_interaction_audit.py -n 6
    GNM_AUDIT_BROWSERS=chromium GNM_AUDIT_TARGETS=parts,capital pytest -m audit tests/e2e/test_interaction_audit.py
    GNM_AUDIT_LABEL=baseline ...   (label recorded in the summary)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import audit_lib as AL  # noqa: E402

pytestmark = [pytest.mark.audit, pytest.mark.browser]

OUT = ROOT / "reports" / "audit"
CELLS = ROOT / "test-results" / "audit_cells"      # bulk per-cell detail: gitignored (only _summary.json is kept)
DATA = ROOT / "docs" / "data"

# route id -> owning view file (for routing failures to the page agents)
VIEW_OF = {
    "mission": "docs/js/views/mission-control.js", "parts": "docs/js/views/parts-intelligence.js",
    "forecast": "docs/js/views/forecast-lab.js", "rotables": "docs/js/views/rotable-repair.js",
    "network": "docs/js/views/network-positioning.js", "capital": "docs/js/views/capital-optimiser.js",
    "aog": "docs/js/views/aog-response-lab.js", "actions": "docs/js/views/planner-action-centre.js",
    "method": "docs/js/views/data-method.js", "about": "docs/js/views/about.js",
    "glossary": "docs/js/views/glossary.js", "planner": "docs/js/views/planner.js",
    "cutaway": "docs/lab/cutaway.js (CUTAWAY)",
}
ROUTES = ["mission", "parts", "forecast", "rotables", "network", "capital", "aog", "actions", "method", "about", "glossary", "planner"]


def _deep_links() -> list[str]:
    """Key deep-link states, with ids taken from the exported data (so they stay valid)."""
    def j(name):
        try:
            return json.loads((DATA / f"{name}.json").read_text())
        except Exception:  # noqa: BLE001
            return {}
    parts = j("parts").get("parts", [])
    rot = next((p["pn"] for p in parts if p.get("cls") == "R"), parts[0]["pn"] if parts else "GN-21-C001")
    aog = (j("aog_lab").get("showcase_ids") or ["AOG-0001"])[0]
    acts = j("actions").get("actions", [])
    ex = acts[0].get("exception_id") if acts else "EX-103-001"
    stations = [s["station"] for s in j("network").get("stations", []) if s.get("role") != "hub"] or ["LHR"]
    return [
        "mission?section=results", f"parts?pn={rot}", "parts?ata=32", f"forecast?pn={rot}", f"rotables?pn={rot}",
        "rotables?view=outstation", f"network?station={stations[0]}", "capital?view=selection&point=I125",
        f"aog?incident={aog}", f"actions?id={ex}", "actions?severity=urgent", "glossary?term=tat",
        "about?section=mro", "method?section=next",
    ]


TARGETS = ROUTES + _deep_links() + ["lab/cutaway.html"]
BROWSERS = ["chromium", "webkit", "firefox"]
MODES = ["simple", "expert"]
VIEWPORTS = [(1440, 900), (390, 844)]


def _env_list(name, default):
    v = os.environ.get(name)
    return [x.strip() for x in v.split(",") if x.strip()] if v else default


def _cells():
    tg = _env_list("GNM_AUDIT_TARGETS", TARGETS)
    tg = [t for t in TARGETS if t in tg or t.split("?")[0] in tg] or tg
    out = []
    for b in _env_list("GNM_AUDIT_BROWSERS", BROWSERS):
        for t in tg:
            for m in _env_list("GNM_AUDIT_MODES", MODES):
                if t.startswith("lab/") and m == "expert":
                    continue  # the cutaway page has no reading mode: audited once per viewport/browser
                for vp in VIEWPORTS:
                    if f"{vp[0]}" not in _env_list("GNM_AUDIT_WIDTHS", ["1440", "390"]):
                        continue
                    out.append((b, t, m, vp))
    if os.environ.get("GNM_AUDIT_RERUN") == "timeouts":
        # re-run only cells whose stored result has click/intercept timeouts (harness artefacts after an audit_lib fix)
        def has_to(c):
            f = CELLS / c[0] / f"{_slug(c[1])}__{c[2]}__{c[3][0]}.json"
            try:
                d = json.loads(f.read_text())
            except Exception:  # noqa: BLE001
                return False
            return any(e["ok"] is False and ("Timeout" in e.get("note", "") or "intercept" in e.get("note", "")) for e in d["elements"])
        out = [c for c in out if has_to(c)]
    return out


def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")


def route_id(t: str) -> str:
    return "cutaway" if t.startswith("lab/") else t.split("?")[0]


# --------------------------------------------------------------------------------------------- browser probe
# (audit_lib itself now opens/closes the 390 px rail, closes open drawers and restores the audited mode.)

_LAUNCH_OK: dict = {}


def browser_available(pw, name: str) -> str | None:
    """None if the browser launches, else the launch error (recorded; e.g. a broken local Firefox build)."""
    if name not in _LAUNCH_OK:
        try:
            getattr(pw, name).launch().close()
            _LAUNCH_OK[name] = None
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            lines = [ln.strip() for ln in msg.splitlines()]
            _LAUNCH_OK[name] = (next((ln for ln in lines if "could not" in ln.lower()), None) or next((ln for ln in lines if "error" in ln.lower()), lines[0]))[:300]
    return _LAUNCH_OK[name]


# --------------------------------------------------------------------------------------------- overlay phase

OVERLAY_SEL = {"modal": ".modal", "story": ".story"}


def _overlay_controls(page, container: str) -> list[dict]:
    found = page.evaluate(AL.DISCOVER_JS, [])
    keep = []
    for d in found:
        try:
            if page.locator(d["selector"]).first.evaluate(f"(e) => !!e.closest({json.dumps(container)})"):
                keep.append(d)
        except Exception:  # noqa: BLE001
            pass
    return keep


FOCUS_ANCHOR_JS = """() => { const c = [...document.querySelectorAll('#view a[href], #view button, .nav-item')].find((e) => {
  const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }); if (c) c.focus(); return !!c; }"""


def _open_overlay(page, base, route, which, anchor=False):
    """Open the help modal / tour. anchor=True first focuses a real control, so focus restoration can be checked."""
    AL._goto(page, base, route)
    if anchor:
        page.evaluate(FOCUS_ANCHOR_JS)
    press = page.keyboard.press if anchor else page.locator("body").press
    if which == "story":
        page.evaluate("window.__gnmTourStepMs = 600000")  # no auto-advance noise while we test the controls
        press("s")
        page.wait_for_selector(".story", timeout=5000)
        page.wait_for_timeout(500)
        try:
            page.evaluate("window.__gnmStory && window.__gnmStory.pause()")
        except Exception:  # noqa: BLE001
            pass
    else:
        press("?")
        page.wait_for_selector(".modal", timeout=3000)
    page.wait_for_timeout(250)
    page.evaluate(AL.OBSERVE_JS)


def audit_overlays(pw, base: str, cfg: AL.AuditConfig) -> tuple[list[AL.ElementResult], dict]:
    """Operate the controls inside the help modal and the guided tour; also map selectors -> shell/view owner."""
    browser, ctx, page, errors = AL._new_page(pw, cfg, base)
    results: list[AL.ElementResult] = []
    shell_map: dict = {}
    try:
        AL._goto(page, base, cfg.route)
        for d in page.evaluate(AL.DISCOVER_JS, []):
            shell_map[d["selector"]] = d["inShell"]
        errors.clear()
        for which, sel in OVERLAY_SEL.items():
            try:
                _open_overlay(page, base, cfg.route, which)
            except Exception as exc:  # noqa: BLE001
                r = AL.ElementResult(id=f"ov-{which}-open", kind="overlay-open", label=f"open {which}", selector=sel,
                                     action="key", ok=False, note=f"could not open: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}",
                                     errors=list(errors))
                errors.clear()
                results.append(r)
                continue
            ctrls = _overlay_controls(page, sel)
            errors.clear()
            for i in range(len(ctrls)):
                d = ctrls[i]
                r = AL.ElementResult(id=f"ov-{which}-{i:02d}", kind="tour" if which == "story" else "overlay-control",
                                     label=d["label"], selector=d["selector"])
                shell_map[d["selector"]] = True
                try:
                    if i:
                        _open_overlay(page, base, cfg.route, which)
                        again = _overlay_controls(page, sel)   # the overlay DOM is rebuilt: re-discover, match by label/index
                        d = next((x for x in again if x["label"] == ctrls[i]["label"]), again[i] if i < len(again) else d)
                        r.selector = d["selector"]
                        page.evaluate(AL.OBSERVE_JS)
                    if which == "story" and re.search(r"\bback\b|previous", d["label"], re.I):
                        page.evaluate("window.__gnmStory && window.__gnmStory.go(1)")   # Back is disabled on step 1
                        page.wait_for_timeout(400)
                        again = _overlay_controls(page, sel)
                        d = next((x for x in again if x["label"] == ctrls[i]["label"]), d)
                        r.selector = d["selector"]
                        page.evaluate(AL.OBSERVE_JS)
                    if d["disabled"]:
                        r.note = "disabled"
                        results.append(r)
                        continue
                    if d["external"]:
                        r.ok, r.note, r.effects = bool(d["href"]), "external link (href checked)", ["external-href"]
                        results.append(r)
                        continue
                    if page.locator(d["selector"]).count() == 0:
                        r.note = "not found after reopen"
                        results.append(r)
                        continue
                    page.evaluate(AL.OBSERVE_JS)
                    before = page.evaluate(AL.STATE_JS)
                    box: list = []
                    r.action = AL._operate(page, d, cfg, box)
                    r.effects, r.ms = AL._wait_effect(page, before, cfg.timeout_ms, box)
                    after = page.evaluate(AL.STATE_JS)
                    if before[which] and not after[which]:
                        r.effects.append(f"{which}-closed")
                    r.ok = bool(r.effects)
                except Exception as exc:  # noqa: BLE001
                    r.ok, r.note = False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
                r.errors = list(errors)
                if errors:
                    r.ok = False
                errors.clear()
                results.append(r)
            # Esc must close the overlay and focus must not fall to <body>
            try:
                _open_overlay(page, base, cfg.route, which, anchor=True)
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                st = page.evaluate(AL.STATE_JS)
                body = page.evaluate("document.activeElement === document.body || !document.activeElement")
                r = AL.ElementResult(id=f"ov-{which}-esc", kind="overlay-esc", label=f"Esc closes {which}", selector=sel, action="key:Escape",
                                     effects=[f"{which}-closed"] if not st[which] else [], ok=(not st[which]) and not body,
                                     note="" if not body else "focus lost to <body> after Esc", errors=list(errors))
                if errors:
                    r.ok = False
                errors.clear()
                results.append(r)
            except Exception as exc:  # noqa: BLE001
                results.append(AL.ElementResult(id=f"ov-{which}-esc", kind="overlay-esc", label=f"Esc closes {which}", selector=sel,
                                                ok=False, note=f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"))
    finally:
        ctx.close()
        browser.close()
    return results, shell_map


# --------------------------------------------------------------------------------------------- one cell


def run_cell(pw, base_index: str, browser: str, target: str, mode: str, vp: tuple[int, int]) -> dict:
    is_lab = target.startswith("lab/")
    base = base_index.rsplit("/", 1)[0] + "/" + target if is_lab else base_index
    route = "" if is_lab else target
    cfg = AL.AuditConfig(route=route, browser=browser, viewport=vp, mode=mode, shortcuts=not is_lab)
    rep = AL.audit_route(pw, base, cfg)
    shell_map: dict = {}
    if not is_lab:
        try:
            extra, shell_map = audit_overlays(pw, base, cfg)
            rep.elements.extend(extra)
        except Exception as exc:  # noqa: BLE001
            rep.elements.append(AL.ElementResult(id="ov-error", kind="overlay-open", label="overlay phase", selector="", ok=False,
                                                 note=f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"))
    d = rep.to_json()
    d["target"] = target
    d["route_id"] = route_id(target)
    for e in d["elements"] + d["shortcuts"]:
        in_shell = shell_map.get(e["selector"])
        if e["kind"] in ("shortcut", "overlay-esc", "overlay-open", "tour") or (e["kind"] == "overlay-control" and e["id"].startswith("ov-")):
            in_shell = True
        e["owner"] = "SHELL (docs/js/app.js / ui.js)" if in_shell and not is_lab else VIEW_OF.get(d["route_id"], d["route_id"])
    return d


# --------------------------------------------------------------------------------------------- aggregate


ABORTED = re.compile(r"requestfailed: .*(cancelled|net::ERR_ABORTED|NS_BINDING_ABORTED)", re.I)


def normalise(c: dict) -> dict:
    """Reclassify two known harness artefacts (recorded in the note, never silently):
    * a request aborted because the harness itself reloaded the page (WebKit reports 'cancelled') is not a site error;
    * clicking the reading-mode radio that is ALREADY selected (Expert in an Expert cell) is a correct no-op."""
    for e in c["elements"] + c["shortcuts"]:
        if e["ok"] is False and e.get("errors") and all(ABORTED.search(x) for x in e["errors"]):
            e["ok"] = bool(e.get("effects")) and "esc-did-not-close" not in e.get("effects", []) and not e.get("note", "").startswith(("Timeout", "Error"))
            e["note"] = (e.get("note", "") + " | ignored: request aborted by the harness reload").strip(" |")
        if e["ok"] is False and e["kind"] == "toggle" and not e.get("errors") and e["label"].strip().lower() == c["mode"] and not e.get("effects"):
            e["ok"], e["note"] = None, "already-selected reading-mode radio (no-op by design)"
    allr = c["elements"] + c["shortcuts"]
    c["summary"].update(ok=sum(r["ok"] is True for r in allr), failed=sum(r["ok"] is False for r in allr), skipped=sum(r["ok"] is None for r in allr))
    return c


def aggregate(label: str | None = None) -> dict:
    cells = []
    for f in sorted(CELLS.glob("*/*.json")):
        try:
            cells.append(normalise(json.loads(f.read_text())))
        except Exception:  # noqa: BLE001
            pass
    fails, by_browser, by_route, by_owner = [], {}, {}, {}
    totals = {"cells": len(cells), "elements": 0, "ok": 0, "failed": 0, "skipped": 0, "load_errors": 0}
    for c in cells:
        b, r = c["browser"], c["route_id"]
        bb = by_browser.setdefault(b, {"cells": 0, "ok": 0, "failed": 0, "skipped": 0, "load_errors": 0})
        rr = by_route.setdefault(r, {"cells": 0, "ok": 0, "failed": 0, "skipped": 0, "load_errors": 0})
        bb["cells"] += 1
        rr["cells"] += 1
        if c.get("load_errors"):
            for agg in (bb, rr, totals):
                agg["load_errors"] += len(c["load_errors"])
            fails.append({"browser": b, "target": c["target"], "mode": c["mode"], "viewport": c["viewport"], "owner": VIEW_OF.get(r, r),
                          "kind": "load", "label": "page load", "selector": "", "note": "; ".join(c["load_errors"])[:400], "errors": c["load_errors"][:5]})
        for e in c["elements"] + c["shortcuts"]:
            key = {True: "ok", False: "failed", None: "skipped"}[e["ok"]]
            for agg in (bb, rr):
                agg[key] += 1
            totals[key] += 1
            totals["elements"] += 1
            if e["ok"] is False:
                o = by_owner.setdefault(e.get("owner", "?"), 0)
                by_owner[e.get("owner", "?")] = o + 1
                fails.append({"browser": b, "target": c["target"], "mode": c["mode"], "viewport": c["viewport"], "owner": e.get("owner", "?"),
                              "kind": e["kind"], "label": e["label"], "selector": e["selector"], "action": e.get("action", ""),
                              "effects": e.get("effects", []), "ms": e.get("ms"), "note": e.get("note", ""), "errors": e.get("errors", [])[:3]})
    unavailable = {f.stem.replace("_unavailable_", ""): f.read_text().strip() for f in OUT.glob("_unavailable_*.txt")}
    prev = {}
    if (OUT / "_summary.json").exists():
        try:
            prev = json.loads((OUT / "_summary.json").read_text())
        except Exception:  # noqa: BLE001
            prev = {}
    data = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label or os.environ.get("GNM_AUDIT_LABEL") or prev.get("label") or "run",
            "effect_timeout_ms": AL.EFFECT_TIMEOUT_MS, "matrix": {"targets": TARGETS, "browsers": BROWSERS, "modes": MODES,
            "viewports": [f"{w}x{h}" for w, h in VIEWPORTS]}, "browsers_unavailable": unavailable, "totals": totals, "by_browser": by_browser, "by_route": by_route,
            "failures_by_owner": dict(sorted(by_owner.items(), key=lambda kv: -kv[1])), "failures": fails,
            "cells": [{"browser": c["browser"], "target": c["target"], "mode": c["mode"], "viewport": c["viewport"], "seconds": c["seconds"],
                       **{k: c["summary"][k] for k in ("total", "ok", "failed", "skipped", "load_errors")}} for c in cells]}
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"._summary.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    os.replace(tmp, OUT / "_summary.json")
    return data


# --------------------------------------------------------------------------------------------- tests


@pytest.fixture(scope="module")
def site():
    with AL.serve_docs() as base:
        yield base


@pytest.fixture(scope="module")
def pw():
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        yield p


CELL_PARAMS = _cells()


@pytest.mark.parametrize("browser,target,mode,vp", CELL_PARAMS,
                         ids=[f"{b}-{_slug(t)}-{m}-{vp[0]}" for b, t, m, vp in CELL_PARAMS])
def test_interaction_cell(site, pw, browser, target, mode, vp):
    err = browser_available(pw, browser)
    if err:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"_unavailable_{browser}.txt").write_text(err + "\n")
        aggregate()
        pytest.skip(f"{browser} could not be launched in this environment: {err}")
    d = run_cell(pw, site, browser, target, mode, vp)
    f = CELLS / browser / f"{_slug(target)}__{mode}__{vp[0]}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    aggregate()
    bad = [f"{e['kind']} {e['label']!r} [{e['owner']}] {e['note']} {e['errors'][:1]}" for e in d["elements"] + d["shortcuts"] if e["ok"] is False]
    assert not d["load_errors"], d["load_errors"]
    assert not bad, f"{len(bad)} failing controls on {target} ({browser} {mode} {vp[0]}):\n" + "\n".join(bad[:40])


if __name__ == "__main__":  # rebuild the aggregate only
    print(json.dumps(aggregate(sys.argv[1] if len(sys.argv) > 1 else None)["totals"]))
