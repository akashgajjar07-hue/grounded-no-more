"""Build reports/INTERACTION_AUDIT.md from the QA JSON outputs.

    python scripts/perf/build_interaction_report.py [--label baseline]

Inputs (whatever exists): reports/audit/_summary.json (interaction matrix), reports/audit/keyboard/_summary.json,
reports/audit/links_downloads.json, reports/audit/numbers_reconcile.json, reports/perf/perf_summary.json.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "reports" / "audit"
P = ROOT / "reports" / "perf"
EXPECTED = {
    "link": "navigates (route change / in-page anchor)", "button": "visible change (DOM / chart / modal / drawer)",
    "tab": "switches the panel", "toggle": "state flips (aria-pressed/checked, re-render)", "select": "view re-renders for the option",
    "slider": "chart / readout updates", "input": "filter / result updates", "term": "tooltip appears",
    "expander": "<details> opens (View data)", "download": "file download starts", "chip": "filter applied",
    "shortcut": "key action (route / help modal / tour; Esc closes)", "tour": "tour step changes / tour closes",
    "overlay-control": "modal control acts (close etc.)", "overlay-esc": "Esc closes overlay, focus not on <body>",
    "overlay-open": "overlay opens", "focusable": "Enter on focusable has an effect", "load": "route loads without console errors",
}


def jl(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")[:160]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    S = jl(A / "_summary.json") or {}
    K = jl(A / "keyboard" / "_summary.json") or {}
    L = jl(A / "links_downloads.json") or {}
    N = jl(A / "numbers_reconcile.json") or {}
    PF = jl(P / "perf_summary.json") or {}
    label = a.label or S.get("label", "run")
    o = [f"# Interaction audit — {label}", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M')} from `reports/audit/_summary.json` (matrix generated {S.get('generated', '—')}), "
         f"`reports/audit/keyboard/`, `reports/audit/links_downloads.json`, `reports/audit/numbers_reconcile.json` and `reports/perf/perf_summary.json`.",
         "", f"**Label: {label}.** Page agents were editing their views while this ran, so failures are a snapshot, not a verdict.", ""]
    # ------------------------------------------------------------ matrix
    t = S.get("totals", {})
    o += ["## 1. Interaction matrix", "",
          "Every route + key deep links + lab/cutaway.html × Simple/Expert × 1440/390 × Chromium/WebKit/Firefox. "
          "Each control must show a visible effect within 1 s; console errors, unhandled rejections and failed requests fail the control. "
          "Help-modal and tour controls are audited in an extra overlay phase.", ""]
    if S.get("browsers_unavailable"):
        for b, why in S["browsers_unavailable"].items():
            o.append(f"> **{b.capitalize()} not run — local launch failure** (`{esc(why)}`; decision V21-FF). Chromium + WebKit only; {b} cells are skipped, not passed.")
        o.append("")
    o += [f"Cells run: **{t.get('cells', 0)}** · controls operated: **{t.get('elements', 0)}** · ok **{t.get('ok', 0)}** · "
          f"**failed {t.get('failed', 0)}** · skipped {t.get('skipped', 0)} · load errors {t.get('load_errors', 0)}", ""]
    o += ["| Browser | cells | ok | failed | skipped | load errors |", "|---|---:|---:|---:|---:|---:|"]
    for b, r in sorted(S.get("by_browser", {}).items()):
        o.append(f"| {b} | {r['cells']} | {r['ok']} | {r['failed']} | {r['skipped']} | {r['load_errors']} |")
    o += ["", "| Route | cells | ok | failed | skipped |", "|---|---:|---:|---:|---:|"]
    for r, x in sorted(S.get("by_route", {}).items(), key=lambda kv: -kv[1]["failed"]):
        o.append(f"| {r} | {x['cells']} | {x['ok']} | {x['failed']} | {x['skipped']} |")
    o += ["", "### Failures by owner", "", "| Owner | failing control-instances |", "|---|---:|"]
    for k, v in S.get("failures_by_owner", {}).items():
        o.append(f"| {esc(k)} | {v} |")
    # group identical failures (same owner/target/control/note) across cells
    groups = defaultdict(list)
    for f in S.get("failures", []):
        key = (f["owner"], f["target"].split("?")[0] if f["kind"] != "load" else f["target"], f["kind"], f["label"], (f.get("note") or "")[:90],
               (f.get("errors") or [""])[0][:90] if f.get("errors") else "")
        groups[key].append(f"{f['browser'][:2]}/{f['mode'][0]}/{f['viewport'].split('x')[0]}")
    o += ["", "### Every failure (grouped: identical control + reason across cells)", "",
          "Cells: `ch`=Chromium `we`=WebKit `fi`=Firefox, `s`/`e` = Simple/Expert, width.", "",
          "| Owner | Page | Control | Kind | Expected effect | Result / reason | Cells |", "|---|---|---|---|---|---|---|"]
    for (owner, page, kind, label_, note, err), cells in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], -len(kv[1]))):
        reason = note or err or "no visible effect within 1 s"
        if err and note:
            reason += f" · {err}"
        o.append(f"| {esc(owner)} | {esc(page)} | {esc(label_)} | {kind} | {EXPECTED.get(kind, 'visible effect')} | FAIL: {esc(reason)} | {len(cells)}: {', '.join(sorted(set(cells)))[:120]} |")
    # pass summary by kind
    kinds = Counter()
    for c in S.get("cells", []):
        pass
    o += ["", "Per-element results (control, expected effect, effect observed, ms, per browser/mode/width) are in "
          "`test-results/audit_cells/<browser>/<cell>.json` (local, gitignored).", ""]
    # ------------------------------------------------------------ keyboard
    o += ["## 2. Keyboard", "", "Chromium, 1440, Simple. Tab walk reaches every control and cycles (no trap); Enter/Space activate; Esc closes overlays with focus restored.", "",
          "| Route | tabbable | reached | cycled | problems | warnings |", "|---|---:|---:|---|---:|---|"]
    kp = []
    for r, x in K.get("routes", {}).items():
        o.append(f"| {r} | {x.get('expected')} | {x.get('reached')} | {x.get('cycled')} | {len(x['problems'])} | {', '.join(x['warnings'])} |")
        kp += [(r, x["owner"], p) for p in x["problems"]]
    if kp:
        o += ["", "| Route | Owner | Problem | Control | Note |", "|---|---|---|---|---|"]
        for r, own, p in kp:
            o.append(f"| {r} | {esc(p.get('owner', own))} | {p['type']} | {esc(p.get('control', ''))} | {esc(p.get('note', ''))} |")
    o.append("")
    # ------------------------------------------------------------ links / downloads
    o += ["## 3. Routes, hard refresh, links and downloads", ""]
    for b in ("chromium", "webkit"):
        r = L.get(f"routes_{b}")
        if r:
            o.append(f"- **Hard refresh ({b})**: {len(r['rows'])} routes/deep links × load/reload/cold-load — {len(r['problems'])} problems.")
            o += [f"  - {esc(p)}" for p in r["problems"][:20]]
    il = L.get("internal_links")
    if il:
        o.append(f"- **Internal links**: {len(il['checked'])} unique hrefs — {len(il['problems'])} problems." + "".join(f"\n  - {esc(p)}" for p in il["problems"][:20]))
    ex = L.get("external_links")
    if ex:
        o.append(f"- **External links**: {ex['checked']} unique URLs, one request each (retry once on network error/429/5xx) — {len(ex['failed'])} failed."
                 + "".join(f"\n  - {esc(f['url'])} → {f.get('status')} {esc(f.get('error', ''))} (on {', '.join(f['found_on'][:2])})" for f in ex["failed"]))
        fl = [r["url"] for r in ex["rows"] if r.get("flaky_retried")]
        if fl:
            o.append(f"  - flaky (needed a retry): {', '.join(fl)}")
    for k in ("downloads_on_disk", "downloads_linked", "download_buttons"):
        if k in L:
            pr = L[k].get("problems")
            o.append(f"- **{k.replace('_', ' ')}**: {'OK' if not pr else pr}")
    db = L.get("download_buttons", {}).get("files", {})
    if db:
        o.append("  - " + "; ".join(f"{k}: {v.get('bytes')} bytes" + (f", {v.get('rows')} CSV rows" if v.get("rows") else "") for k, v in db.items()))
    o.append("")
    # ------------------------------------------------------------ numbers
    o += ["## 4. Numbers reconcile (site ↔ data ↔ README ↔ workbook ↔ deck)", ""]
    for k, v in N.items():
        if k in ("generated", "truth"):
            continue
        pr = v if isinstance(v, list) else v.get("problems", [])
        w = [] if isinstance(v, list) else (v.get("warnings") or v.get("warnings_untraced_hour_figures") or [])
        o.append(f"- **{k}**: {'OK' if not pr else '; '.join(map(esc, pr[:8]))}" + (f" · warnings: {esc(w)}" if w else ""))
    if "workbook" in N:
        o.append(f"  - workbook 'Site data' line: {esc(N['workbook'].get('site_data_line'))} vs kpis.json {N['workbook'].get('kpis_meta')} (git {N['workbook'].get('kpis_git')})")
    o.append("")
    # ------------------------------------------------------------ perf
    o += ["## 5. Performance (§2.9)", ""]
    if PF:
        o.append(f"Lighthouse ran: **{'yes' if PF.get('lighthouse_available') else 'no — fallback Playwright + CDP'}** "
                 f"(lighthouse@12 via npx, Playwright Chromium as CHROME_PATH, headless). Targets: Performance ≥ 85, Accessibility ≥ 90, CLS < 0.05.")
        o.append(f"Pages: landing + the two heaviest workspaces by view JS + JSON bytes: **{', '.join(PF.get('lighthouse_targets', []))}**.")
        o += ["", "| Page | preset | Performance | Accessibility | CLS | LCP ms | TBT ms |", "|---|---|---:|---:|---:|---:|---:|"]
        for k, r in PF.get("lighthouse", {}).items():
            pg, pre = k.split(":")
            if r.get("ok"):
                o.append(f"| {pg} | {pre} | {r['performance']} | {r['accessibility']} | {r['cls']:.3f} | {round(r['lcp_ms'] or 0)} | {round(r['tbt_ms'] or 0)} |")
            else:
                o.append(f"| {pg} | {pre} | — | — | — | — | — (error: {esc(r.get('error'))[:80]}) |")
        lhs = jl(P / "lighthouse_summary.json") or {}
        a11y = {f["title"] for r in lhs.get("results", {}).values() for f in r.get("a11y_failures", [])}
        if a11y:
            o += ["", "Accessibility audits not passing (any target page): " + "; ".join(sorted(a11y))]
        o += ["", f"**CLS on load** (layout-shift observer, 5 s, every route at 1440 and 390): max **{PF.get('cls_max')}**."]
        worst = sorted(PF.get("cls_on_load", {}).items(), key=lambda kv: -kv[1]["cls"])[:6]
        o.append("Worst: " + ", ".join(f"{k} {v['cls']}" for k, v in worst))
        o += ["", "**Animations** (rAF frame sampler + longtask observer; headless Chromium; ×4 = CDP CPU throttling):", "",
              "| Scenario | fps | frame p50 / p95 / max ms | frames > 33 ms | long tasks > 50 / > 200 ms | longest task ms |", "|---|---:|---|---:|---|---:|"]
        for k, r in PF.get("animations", {}).items():
            if "error" in r:
                o.append(f"| {k} | — | error: {esc(r['error'])} | | | |")
            else:
                o.append(f"| {k} | {r['fps']} | {r['frame_p50_ms']} / {r['frame_p95_ms']} / {r['frame_max_ms']} | {r['frames_over_33ms']} | "
                         f"{r['longtasks_over_50ms']} / {r['longtasks_over_200ms']} | {r['longest_task_ms']} |")
        o += ["", "Weights (view JS / JSON bytes): " + ", ".join(f"{k} {v['view_js_bytes'] // 1024}k/{v['json_bytes'] // 1024}k" for k, v in PF.get("weights", {}).items())]
        o += ["", "Verdicts:", "```", json.dumps(PF.get("verdicts", {}), indent=1), "```"]
    else:
        o.append("Not run yet: `python scripts/perf/run_perf.py`.")
    o += ["", "## How to re-run", "", "```",
          "pytest -m audit tests/e2e/test_interaction_audit.py -n 6        # matrix -> reports/audit/_summary.json",
          "pytest tests/e2e/test_links_downloads.py tests/e2e/test_keyboard.py tests/e2e/test_numbers_reconcile_ui.py",
          "pytest -m audit tests/e2e/test_links_downloads.py -k external   # network",
          "python scripts/perf/run_perf.py --label <label>",
          "python scripts/perf/build_interaction_report.py --label <label>", "```", ""]
    (ROOT / "reports" / "INTERACTION_AUDIT.md").write_text("\n".join(o))
    print("wrote reports/INTERACTION_AUDIT.md")


if __name__ == "__main__":
    main()
