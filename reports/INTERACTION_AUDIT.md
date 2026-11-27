# Interaction audit — final-v2.2

Generated 2026-11-27 22:02 from `reports/audit/_summary.json` (matrix generated 2026-11-27T22:01:50), `reports/audit/keyboard/`, `reports/audit/links_downloads.json`, `reports/audit/numbers_reconcile.json` and `reports/perf/perf_summary.json`.

**Label: final-v2.2.** Run on the frozen v2.2 tree. Stopped at the release time limit: 91 cells completed (Chromium 68, WebKit 23), 0 failed; the cells not run are listed in section 1b.

## 1. Interaction matrix

Every route + key deep links + lab/cutaway.html × Simple/Expert: Chromium at 1440 and 390, WebKit at 1440 plus a 390 phone smoke (Firefox: see note). Each control must show a visible effect within 1 s; console errors, unhandled rejections and failed requests fail the control. Help-modal and tour controls are audited in an extra overlay phase.

> **Firefox not run — local launch failure** (`[pid=86274][err] Could not find profile folder.`; decision V21-FF). Chromium + WebKit only; firefox cells are skipped, not passed.

Cells run: **91** · controls operated: **6312** · ok **6072** · **failed 0** · skipped 240 · load errors 0

| Browser | cells | ok | failed | skipped | load errors |
|---|---:|---:|---:|---:|---:|
| chromium | 68 | 4608 | 0 | 200 | 0 |
| webkit | 23 | 1464 | 0 | 40 | 0 |

| Route | cells | ok | failed | skipped |
|---|---:|---:|---:|---:|
| about | 10 | 586 | 0 | 0 |
| actions | 11 | 728 | 0 | 173 |
| aog | 5 | 352 | 0 | 0 |
| capital | 8 | 643 | 0 | 0 |
| forecast | 7 | 528 | 0 | 14 |
| glossary | 12 | 556 | 0 | 0 |
| cutaway | 4 | 108 | 0 | 0 |
| method | 7 | 510 | 0 | 0 |
| mission | 12 | 858 | 0 | 0 |
| network | 4 | 338 | 0 | 28 |
| planner | 5 | 232 | 0 | 0 |
| rotables | 6 | 633 | 0 | 25 |

**Totals per route × browser** (ok / failed / skipped, summed over modes, widths and deep links of that route):

| Route | chromium | webkit |
|---|---|---|
| about | 468 / **0** / 0 (8 cells) | 118 / **0** / 0 (2 cells) |
| actions | 598 / **0** / 141 (9 cells) | 130 / **0** / 32 (2 cells) |
| aog | 282 / **0** / 0 (4 cells) | 70 / **0** / 0 (1 cells) |
| capital | 474 / **0** / 0 (6 cells) | 169 / **0** / 0 (2 cells) |
| cutaway | 54 / **0** / 0 (2 cells) | 54 / **0** / 0 (2 cells) |
| forecast | 380 / **0** / 10 (5 cells) | 148 / **0** / 4 (2 cells) |
| glossary | 372 / **0** / 0 (8 cells) | 184 / **0** / 0 (4 cells) |
| method | 357 / **0** / 0 (5 cells) | 153 / **0** / 0 (2 cells) |
| mission | 572 / **0** / 0 (8 cells) | 286 / **0** / 0 (4 cells) |
| network | 338 / **0** / 28 (4 cells) | 0 / **0** / 0 (0 cells) |
| planner | 186 / **0** / 0 (4 cells) | 46 / **0** / 0 (1 cells) |
| rotables | 527 / **0** / 21 (5 cells) | 106 / **0** / 4 (1 cells) |

**Fixed since the baseline** (2026-11-26T20:25:40: 714 failing control-instances → 0 now): 332 distinct (page, control) pairs no longer fail, e.g. about · Capital Optimiser6; about · Network Positioning5; about · Rotable & Repair4; about · Esc closes story; about · key 3; about · key 4; about?section=mro · Forecast Lab3; about?section=mro · Network Positioning5; about?section=mro · What real data would make this useful; about?section=mro · Esc closes story; about?section=mro · key 4; actions · Rotable & Repair4; actions · Esc closes story; actions · key 3; actions · key 5; actions?id=EX-103-001 · Keyboard shortcuts; actions?id=EX-103-001 · Open navigation; actions?id=EX-103-001 · Capital Optimiser6; actions?id=EX-103-001 · Data & Method0; actions?id=EX-103-001 · GROUNDED NO MORE — Mission Control; actions?id=EX-103-001 · Glossary; actions?id=EX-103-001 · Parts Intelligence2; actions?id=EX-103-001 · Planner Action Centre8; actions?id=EX-103-001 · Rotable & Repair4; actions?id=EX-103-001 · Close …

### Failures by owner

| Owner | failing control-instances |
|---|---:|

### Every failure (grouped: identical control + reason across cells)

Cells: `ch`=Chromium `we`=WebKit `fi`=Firefox, `s`/`e` = Simple/Expert, width.

| Owner | Page | Control | Kind | Expected effect | Result / reason | Cells |
|---|---|---|---|---|---|---|

Per-element results (control, expected effect, effect observed, ms, per browser/mode/width) are in `test-results/audit_cells/<browser>/<cell>.json` (local, gitignored).

## 1b. Cells not completed — time limit

The release time limit stopped the run before these cells ran. They are **not completed**, not passed.

**Parts (all cells).** The first parts cells (Chromium 1440/390, WebKit 1440) found a real bug: 7 ATA badges at 1440 and 2 at 390 had a dead gap between the circle and the status word beside it, so a click in that gap did nothing. Fixed in ede9626, which adds a transparent hit area over the circle and the word. Those pre-fix cells are superseded and not counted above. The fix is covered by the 35 passing tests in tests/test_site_parts.py, plus a targeted check: in Chromium and WebKit at 1440 and 390, clicking the centre of each of the 8 badges selects its system, and Playwright's own locator click succeeds. The full parts audit cells were not re-run.

**Chromium: 38 cells not completed — time limit.**

- parts · simple · 1440
- parts · simple · 390
- parts · expert · 1440
- parts · expert · 390
- parts?pn=GN-21-R001 · simple · 1440
- parts?pn=GN-21-R001 · simple · 390
- parts?pn=GN-21-R001 · expert · 1440
- parts?pn=GN-21-R001 · expert · 390
- parts?ata=32 · simple · 1440
- parts?ata=32 · simple · 390
- parts?ata=32 · expert · 1440
- parts?ata=32 · expert · 390
- forecast?pn=GN-21-R001 · simple · 390
- forecast?pn=GN-21-R001 · expert · 1440
- forecast?pn=GN-21-R001 · expert · 390
- rotables?pn=GN-21-R001 · simple · 390
- rotables?pn=GN-21-R001 · expert · 1440
- rotables?pn=GN-21-R001 · expert · 390
- rotables?view=outstation · simple · 1440
- rotables?view=outstation · simple · 390
- rotables?view=outstation · expert · 1440
- rotables?view=outstation · expert · 390
- network?station=LHR · simple · 1440
- network?station=LHR · simple · 390
- network?station=LHR · expert · 1440
- network?station=LHR · expert · 390
- capital?view=selection&point=I125 · expert · 1440
- capital?view=selection&point=I125 · expert · 390
- aog?incident=AOG-0001 · simple · 1440
- aog?incident=AOG-0001 · simple · 390
- aog?incident=AOG-0001 · expert · 1440
- aog?incident=AOG-0001 · expert · 390
- actions?severity=urgent · simple · 390
- actions?severity=urgent · expert · 1440
- actions?severity=urgent · expert · 390
- method?section=next · simple · 390
- method?section=next · expert · 1440
- method?section=next · expert · 390

**Webkit: 35 cells not completed — time limit.**

- parts · simple · 1440
- parts · expert · 1440
- rotables · expert · 1440
- network · simple · 1440
- network · expert · 1440
- aog · expert · 1440
- about · simple · 1440
- about · expert · 1440
- planner · expert · 1440
- mission?section=results · simple · 1440
- mission?section=results · expert · 1440
- parts?pn=GN-21-R001 · simple · 1440
- parts?pn=GN-21-R001 · expert · 1440
- parts?ata=32 · simple · 1440
- parts?ata=32 · expert · 1440
- forecast?pn=GN-21-R001 · simple · 1440
- forecast?pn=GN-21-R001 · expert · 1440
- rotables?pn=GN-21-R001 · simple · 1440
- rotables?pn=GN-21-R001 · expert · 1440
- rotables?view=outstation · simple · 1440
- rotables?view=outstation · expert · 1440
- network?station=LHR · simple · 1440
- network?station=LHR · expert · 1440
- capital?view=selection&point=I125 · simple · 1440
- capital?view=selection&point=I125 · expert · 1440
- aog?incident=AOG-0001 · simple · 1440
- aog?incident=AOG-0001 · expert · 1440
- actions?id=EX-103-001 · simple · 1440
- actions?id=EX-103-001 · expert · 1440
- actions?severity=urgent · simple · 1440
- actions?severity=urgent · expert · 1440
- about?section=mro · simple · 1440
- about?section=mro · expert · 1440
- method?section=next · simple · 1440
- method?section=next · expert · 1440

## 2. Keyboard

Chromium, 1440, Simple. Tab walk reaches every control and cycles (no trap); Enter/Space activate; Esc closes overlays with focus restored.

| Route | tabbable | reached | cycled | problems | warnings |
|---|---:|---:|---|---:|---|
| about | 39 | 39 | True | 0 |  |
| actions | 60 | 60 | True | 0 |  |
| aog | 40 | 40 | True | 0 |  |
| capital | 63 | 63 | True | 0 | tab-stops-on-non-semantic-elements, upward-jump>400px |
| forecast | 57 | 57 | True | 0 | upward-jump>400px |
| glossary | 27 | 27 | True | 0 |  |
| method | 36 | 36 | True | 0 |  |
| mission | 52 | 52 | True | 0 | tab-stops-on-non-semantic-elements |
| network | 77 | 77 | True | 0 | upward-jump>400px |
| parts | 124 | 124 | True | 0 | upward-jump>400px |
| planner | 27 | 27 | True | 0 |  |
| rotables | 91 | 91 | True | 0 | upward-jump>400px |

## 3. Routes, hard refresh, links and downloads

- **Hard refresh (chromium)**: 26 routes/deep links × load/reload/cold-load — 0 problems.
- **Hard refresh (webkit)**: 26 routes/deep links × load/reload/cold-load — 0 problems.
- **Internal links**: 59 unique hrefs — 0 problems.
- **downloads on disk**: OK
- **downloads linked**: OK
- **download buttons**: OK
  - downloads/grounded_no_more_planner_workbook.xlsx: 120028 bytes; downloads/case_study_deck.pdf: 1694536 bytes; actions:export-csv: 36103 bytes, 64 CSV rows

## 4. Numbers reconcile (site ↔ data ↔ README ↔ workbook ↔ deck)

- **site_capital_mission?section=results**: OK
- **site_capital_capital**: OK
- **site_kpis**: OK
- **site_names**: OK
- **readme**: OK · warnings: ['1,181']
- **workbook**: OK
- **deck**: OK · warnings: ["presentations/case_study_deck.pptx: hour figures not found in docs/data (check by hand): ['1,123']"]
  - workbook 'Site data' line: docs/data/*.json, exported 2026-11-27T13:15:58Z (release v2.2) vs kpis.json 2026-11-27T13:15:58Z (release v2.2)

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
