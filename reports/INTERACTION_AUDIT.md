# Interaction audit — final-v2.1

Generated 2026-11-27 01:05 from `reports/audit/_summary.json` (matrix generated 2026-11-27T01:05:01), `reports/audit/keyboard/`, `reports/audit/links_downloads.json`, `reports/audit/numbers_reconcile.json` and `reports/perf/perf_summary.json`.

**Label: final-v2.1.** Final run on frozen code (commit 7ea0d58), sharded over 8–9 parallel workers. Disabled controls: **none**.

## 1. Interaction matrix

Every route + key deep links + lab/cutaway.html. Chromium: × Simple/Expert × 1440/390. WebKit: × Simple/Expert at 1440, plus a 390 smoke of the landing (incl. tour) and the cutaway. Each control must show a visible effect within 1 s; console errors, unhandled rejections and failed requests fail the control. Help-modal and tour controls are audited in an extra overlay phase.

> **Firefox not run — local launch failure** (`[pid=86274][err] Could not find profile folder.`; decision V21-FF). Chromium + WebKit only; firefox cells are skipped, not passed.

Cells run: **162** · controls operated: **12853** · ok **12228** · **failed 0** · skipped 625 · load errors 0

| Browser | cells | ok | failed | skipped | load errors |
|---|---:|---:|---:|---:|---:|
| chromium | 106 | 8070 | 0 | 444 | 0 |
| webkit | 56 | 4158 | 0 | 181 | 0 |

| Route | cells | ok | failed | skipped |
|---|---:|---:|---:|---:|
| about | 12 | 628 | 0 | 0 |
| actions | 18 | 1212 | 0 | 252 |
| aog | 12 | 820 | 0 | 12 |
| capital | 12 | 956 | 0 | 12 |
| forecast | 12 | 902 | 0 | 36 |
| glossary | 12 | 556 | 0 | 0 |
| cutaway | 4 | 108 | 0 | 0 |
| method | 12 | 874 | 0 | 12 |
| mission | 14 | 972 | 0 | 14 |
| network | 12 | 988 | 0 | 54 |
| parts | 18 | 2058 | 0 | 152 |
| planner | 6 | 278 | 0 | 0 |
| rotables | 18 | 1876 | 0 | 81 |

**Totals per route × browser** (ok / failed / skipped, summed over modes, widths and deep links of that route):

| Route | chromium | webkit |
|---|---|---|
| about | 420 / **0** / 0 (8 cells) | 208 / **0** / 0 (4 cells) |
| actions | 810 / **0** / 168 (12 cells) | 402 / **0** / 84 (6 cells) |
| aog | 552 / **0** / 8 (8 cells) | 268 / **0** / 4 (4 cells) |
| capital | 626 / **0** / 8 (8 cells) | 330 / **0** / 4 (4 cells) |
| cutaway | 54 / **0** / 0 (2 cells) | 54 / **0** / 0 (2 cells) |
| forecast | 608 / **0** / 24 (8 cells) | 294 / **0** / 12 (4 cells) |
| glossary | 372 / **0** / 0 (8 cells) | 184 / **0** / 0 (4 cells) |
| method | 580 / **0** / 8 (8 cells) | 294 / **0** / 4 (4 cells) |
| mission | 556 / **0** / 8 (8 cells) | 416 / **0** / 6 (6 cells) |
| network | 668 / **0** / 36 (8 cells) | 320 / **0** / 18 (4 cells) |
| parts | 1385 / **0** / 130 (12 cells) | 673 / **0** / 22 (6 cells) |
| planner | 186 / **0** / 0 (4 cells) | 92 / **0** / 0 (2 cells) |
| rotables | 1253 / **0** / 54 (12 cells) | 623 / **0** / 27 (6 cells) |

**Disabled controls seen (skipped, not failed):** actions: Back (18 cells); actions: Clear filters (12 cells)

**Fixed since the baseline** (2026-11-26T20:25:40: 714 failing control-instances → 0 now): 332 distinct (page, control) pairs no longer fail, e.g. about · Capital Optimiser6; about · Network Positioning5; about · Rotable & Repair4; about · Esc closes story; about · key 3; about · key 4; about?section=mro · Forecast Lab3; about?section=mro · Network Positioning5; about?section=mro · What real data would make this useful; about?section=mro · Esc closes story; about?section=mro · key 4; actions · Rotable & Repair4; actions · Esc closes story; actions · key 3; actions · key 5; actions?id=EX-103-001 · Keyboard shortcuts; actions?id=EX-103-001 · Open navigation; actions?id=EX-103-001 · Capital Optimiser6; actions?id=EX-103-001 · Data & Method0; actions?id=EX-103-001 · GROUNDED NO MORE — Mission Control; actions?id=EX-103-001 · Glossary; actions?id=EX-103-001 · Parts Intelligence2; actions?id=EX-103-001 · Planner Action Centre8; actions?id=EX-103-001 · Rotable & Repair4; actions?id=EX-103-001 · Close …

### Failures by owner

| Owner | failing control-instances |
|---|---:|

### Every failure (grouped: identical control + reason across cells)

Cells: `ch`=Chromium `we`=WebKit `fi`=Firefox, `s`/`e` = Simple/Expert, width.

| Owner | Page | Control | Kind | Expected effect | Result / reason | Cells |
|---|---|---|---|---|---|---|

Per-element results (control, expected effect, effect observed, ms, per browser/mode/width) are in `test-results/audit_cells/<browser>/<cell>.json` (local, gitignored).

## 2. Keyboard

Chromium, 1440, Simple. Tab walk reaches every control and cycles (no trap); Enter/Space activate; Esc closes overlays with focus restored.

| Route | tabbable | reached | cycled | problems | warnings |
|---|---:|---:|---|---:|---|
| about | 33 | 33 | True | 0 |  |
| actions | 60 | 60 | True | 0 |  |
| aog | 39 | 39 | True | 0 |  |
| capital | 62 | 62 | True | 0 | tab-stops-on-non-semantic-elements, upward-jump>400px |
| forecast | 57 | 57 | True | 0 | upward-jump>400px |
| glossary | 27 | 27 | True | 0 |  |
| method | 34 | 34 | True | 0 |  |
| mission | 50 | 50 | True | 0 | tab-stops-on-non-semantic-elements |
| network | 76 | 76 | True | 0 | upward-jump>400px |
| parts | 125 | 125 | True | 5 | upward-jump>400px |
| planner | 27 | 27 | True | 0 |  |
| rotables | 91 | 91 | True | 0 | upward-jump>400px |

| Route | Owner | Problem | Control | Note |
|---|---|---|---|---|
| parts | docs/js/views/parts-intelligence.js | Space-no-effect | GN-32-C009 steady, ADI 1.05, CV² 0.47 |  |
| parts | docs/js/views/parts-intelligence.js | Space-no-effect | GN-32-C030 steady, ADI 1.01, CV² 0.48 |  |
| parts | docs/js/views/parts-intelligence.js | Space-no-effect | GN-32-E011 now and then, ADI 2.61, CV² 0.16 |  |
| parts | docs/js/views/parts-intelligence.js | Space-no-effect | GN-32-R014 now and then, ADI 2.38, CV² 0.20 |  |
| parts | docs/js/views/parts-intelligence.js | Space-no-effect | GN-32-R036 now and then, ADI 1.44, CV² 0.27 |  |

## 3. Routes, hard refresh, links and downloads

- **Hard refresh (chromium)**: 26 routes/deep links × load/reload/cold-load — 0 problems.
- **Hard refresh (webkit)**: 26 routes/deep links × load/reload/cold-load — 0 problems.
- **Internal links**: 59 unique hrefs — 0 problems.
- **External links**: 14 unique URLs, one request each (retry once on network error/429/5xx) — 0 failed.
- **downloads on disk**: OK
- **downloads linked**: OK
- **download buttons**: OK
  - downloads/grounded_no_more_planner_workbook.xlsx: 119589 bytes; downloads/case_study_deck.pdf: 1693301 bytes; actions:export-csv: 36103 bytes, 64 CSV rows

## 4. Numbers reconcile (site ↔ data ↔ README ↔ workbook ↔ deck)

- **site_capital_mission?section=results**: OK
- **site_capital_capital**: OK
- **site_kpis**: OK
- **site_names**: OK
- **readme**: OK · warnings: ['1,181']
- **workbook**: OK
- **deck**: OK · warnings: ["presentations/case_study_deck.pptx: hour figures not found in docs/data (check by hand): ['1,123']"]
  - workbook 'Site data' line: docs/data/*.json, exported 2026-11-26T12:46:35Z (git f49a029) vs kpis.json 2026-11-26T13:02:18Z (git 390aee8)

## 5. Performance (§2.9)

Lighthouse ran: **yes** (lighthouse@12 via npx, Playwright Chromium as CHROME_PATH, headless). Targets: Performance ≥ 85, Accessibility ≥ 90, CLS < 0.05.
Pages: landing + the two heaviest workspaces by view JS + JSON bytes: **mission, parts, forecast**.

| Page | preset | Performance | Accessibility | CLS | LCP ms | TBT ms |
|---|---|---:|---:|---:|---:|---:|
| mission | mobile | 92 | 100 | 0.014 | 3303 | 0 |
| mission | desktop | 100 | 100 | 0.001 | 642 | 0 |
| parts | mobile | 91 | 92 | 0.005 | 3460 | 81 |
| parts | desktop | 100 | 96 | 0.001 | 647 | 0 |
| forecast | mobile | 92 | 100 | 0.005 | 3389 | 36 |
| forecast | desktop | 100 | 100 | 0.001 | 646 | 0 |

Accessibility audits not passing (any target page): Background and foreground colors do not have a sufficient contrast ratio.; Elements with visible text labels do not have matching accessible names.; Heading elements are not in a sequentially-descending order; Lists do not contain only `<li>` elements and script supporting elements (`<script>` and `<template>`).; Uses ARIA roles on incompatible elements

**CLS on load** (layout-shift observer, 5 s, every route at 1440 and 390): max **0.0282**.
Worst: capital@390 0.0282, rotables@390 0.0059, parts@390 0.0049, network@390 0.0049, about@390 0.0049, mission@390 0.0048

**Animations** (rAF frame sampler + longtask observer; headless Chromium; ×4 = CDP CPU throttling):

| Scenario | fps | frame p50 / p95 / max ms | frames > 33 ms | long tasks > 50 / > 200 ms | longest task ms |
|---|---:|---|---:|---|---:|
| tour@x1 | 59.8 | 16.7 / 16.8 / 33.4 | 0 | 0 / 0 | 0 |
| slider@x1 | 59.5 | 16.7 / 16.8 / 33.3 | 0 | 0 / 0 | 0 |
| cutaway@x1 | 59.8 | 16.7 / 16.7 / 16.8 | 0 | 0 / 0 | 0 |
| tour@x4 | 59.0 | 16.7 / 16.8 / 133.3 | 7 | 3 / 0 | 109 |
| slider@x4 | 58.4 | 16.7 / 16.8 / 33.4 | 1 | 0 / 0 | 0 |
| cutaway@x4 | 59.7 | 16.7 / 16.7 / 33.4 | 0 | 0 / 0 | 0 |

Weights (view JS / JSON bytes): mission 0k/0k, parts 0k/0k, forecast 0k/0k, rotables 0k/0k, network 0k/0k, capital 0k/0k, aog 0k/0k, actions 0k/0k, method 0k/0k, about 0k/0k, glossary 0k/0k, planner 0k/0k

Verdicts:
```
{
 "lighthouse mission:mobile": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": true
 },
 "lighthouse mission:desktop": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": true
 },
 "lighthouse parts:mobile": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": true
 },
 "lighthouse parts:desktop": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": true
 },
 "lighthouse forecast:mobile": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": true
 },
 "lighthouse forecast:desktop": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": true
 },
 "cls_on_load<0.05 (all routes)": true,
 "anim tour@x1": {
  "no longtask>200ms": true,
  "fps>=55": true
 },
 "anim slider@x1": {
  "no longtask>200ms": true,
  "fps>=55": true
 },
 "anim cutaway@x1": {
  "no longtask>200ms": true,
  "fps>=55": true
 },
 "anim tour@x4": {
  "no longtask>200ms": true,
  "fps>=55": true
 },
 "anim slider@x4": {
  "no longtask>200ms": true,
  "fps>=55": true
 },
 "anim cutaway@x4": {
  "no longtask>200ms": true,
  "fps>=55": true
 }
}
```

## How to re-run

```
pytest -m audit tests/e2e/test_interaction_audit.py -n 6        # matrix -> reports/audit/_summary.json
pytest tests/e2e/test_links_downloads.py tests/e2e/test_keyboard.py tests/e2e/test_numbers_reconcile_ui.py
pytest -m audit tests/e2e/test_links_downloads.py -k external   # network
python scripts/perf/run_perf.py --label <label>
python scripts/perf/build_interaction_report.py --label <label>
```
