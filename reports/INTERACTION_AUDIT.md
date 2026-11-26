# Interaction audit — baseline

Generated 2026-11-26 20:16 from `reports/audit/_summary.json` (matrix generated 2026-11-26T20:11:07), `reports/audit/keyboard/`, `reports/audit/links_downloads.json`, `reports/audit/numbers_reconcile.json` and `reports/perf/perf_summary.json`.

**Label: baseline.** Page agents were editing their views while this ran, so failures are a snapshot, not a verdict.

## 1. Interaction matrix

Every route + key deep links + lab/cutaway.html × Simple/Expert × 1440/390 × Chromium/WebKit/Firefox. Each control must show a visible effect within 1 s; console errors, unhandled rejections and failed requests fail the control. Help-modal and tour controls are audited in an extra overlay phase.

> **Firefox not run — local launch failure** (`[pid=86274][err] Could not find profile folder.`; decision V21-FF). Chromium + WebKit only; firefox cells are skipped, not passed.

Cells run: **212** · controls operated: **17017** · ok **15122** · **failed 875** · skipped 1020 · load errors 2

| Browser | cells | ok | failed | skipped | load errors |
|---|---:|---:|---:|---:|---:|
| chromium | 106 | 7546 | 461 | 502 | 0 |
| webkit | 106 | 7576 | 414 | 518 | 2 |

| Route | cells | ok | failed | skipped |
|---|---:|---:|---:|---:|
| parts | 24 | 2510 | 204 | 316 |
| rotables | 24 | 2310 | 172 | 132 |
| method | 16 | 1050 | 110 | 16 |
| network | 16 | 1223 | 97 | 88 |
| actions | 24 | 1540 | 80 | 336 |
| mission | 16 | 1050 | 46 | 16 |
| aog | 16 | 1053 | 35 | 32 |
| forecast | 16 | 1191 | 30 | 48 |
| glossary | 16 | 716 | 28 | 0 |
| cutaway | 4 | 83 | 25 | 0 |
| about | 16 | 819 | 21 | 0 |
| capital | 16 | 1213 | 19 | 36 |
| planner | 8 | 364 | 8 | 0 |

### Failures by owner

| Owner | failing control-instances |
|---|---:|
| SHELL (docs/js/app.js / ui.js) | 372 |
| docs/js/views/rotable-repair.js | 143 |
| docs/js/views/data-method.js | 100 |
| docs/js/views/parts-intelligence.js | 89 |
| docs/js/views/network-positioning.js | 79 |
| docs/js/views/mission-control.js | 29 |
| docs/lab/cutaway.js (CUTAWAY) | 25 |
| docs/js/views/aog-response-lab.js | 15 |
| docs/js/views/forecast-lab.js | 10 |
| docs/js/views/glossary.js | 7 |
| docs/js/views/about.js | 6 |

### Every failure (grouped: identical control + reason across cells)

Cells: `ch`=Chromium `we`=WebKit `fi`=Firefox, `s`/`e` = Simple/Expert, width.

| Owner | Page | Control | Kind | Expected effect | Result / reason | Cells |
|---|---|---|---|---|---|---|
| SHELL (docs/js/app.js / ui.js) | about | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 3 not found | 3: we/e/1440, we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | about | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 226 not found | 2: ch/e/390, ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | about | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1 not found | 2: we/e/1440, we/e/390 |
| SHELL (docs/js/app.js / ui.js) | about | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 154 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | about | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 25 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | about | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 19 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | about | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 106 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | about | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 73 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | about | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 105 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | about | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 108 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | about | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 156 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | actions | GROUNDED NO MORE — Mission Control | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Planner Action Centre8 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Parts Intelligence2 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Data & Method0 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Glossary | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Simple | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Keyboard shortcuts | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | GROUNDED NO MORE — Mission Control | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Planner Action Centre8 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Parts Intelligence2 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Data & Method0 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Glossary | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Open navigation | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 115 not found | 2: we/e/1440, we/e/390 |
| SHELL (docs/js/app.js / ui.js) | actions | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 890 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 742 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 957 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 217 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | actions | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 810 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | actions | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 770 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | actions | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 187 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | AOG Response Lab7 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | actions | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 89 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | actions | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 3: we/e/1440, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 3 not found | 3: we/e/1440, we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 253 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 153 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 204 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 229 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 154 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | aog | key 8 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 279 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 154 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | Parts Intelligence2 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 100 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 3 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 25 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | aog | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 105 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | aog | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 71 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | capital | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 19 not found | 4: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 13 not found | 2: we/e/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | capital | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 15 not found | 2: we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | capital | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 344 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | key 7 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 396 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 415 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | capital | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: console.error: unhandledrejection: Cannot read properties of null (reading 'getBoundingCli | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 23 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | 60-second tourS | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | capital | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 124 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 49 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | capital | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 140 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | capital | Back | tour | tour step changes / tour closes | FAIL: console.error: SyntaxError: Importing binding name 'tx' is not found. | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | capital | Next | tour | tour step changes / tour closes | FAIL: console.error: SyntaxError: Importing binding name 'tx' is not found. | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 290 not found | 3: we/e/1440, we/e/390, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 365 not found | 2: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 144 not found | 2: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 3123 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: console.error: unhandledrejection: Cannot read properties of null (reading 'getBoundingCli | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 3090 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 3097 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 3019 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | Back | tour | tour step changes / tour closes | FAIL: console.error: SyntaxError: Importing binding name 'tx' is not found. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | Next | tour | tour step changes / tour closes | FAIL: console.error: SyntaxError: Importing binding name 'tx' is not found. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 533 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 600 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 721 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | forecast | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 731 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | forecast | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 292 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 3 not found | 5: ch/s/390, we/e/1440, we/e/390, we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 154 not found | 2: ch/e/1440, ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 3 not found | 2: we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 2: we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: console.error: SyntaxError: The requested module '../lib/motion.js' does not provide an ex | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | glossary | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: console.error: SyntaxError: The requested module '../lib/motion.js' does not provide an ex | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: console.error: SyntaxError: The requested module '../lib/motion.js' does not provide an ex | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | glossary | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: console.error: unhandledrejection: Cannot read properties of null (reading 'getBoundingCli | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 0 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 90 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | glossary | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 90 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 74 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | glossary | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 33 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | glossary | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 76 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | method | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 3 not found | 3: we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | method | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1 not found | 2: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | method | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | method | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 90 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | method | Back | tour | tour step changes / tour closes | FAIL: console.error: SyntaxError: Importing binding name 'tx' is not found. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | method | Next | tour | tour step changes / tour closes | FAIL: console.error: SyntaxError: Importing binding name 'tx' is not found. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | method | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 17 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | mission | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 3 not found | 5: we/e/1440, we/e/390, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | mission | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 17 not found | 3: we/e/1440, we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | mission | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 92 not found | 3: we/e/1440, we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | mission | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 74 not found | 2: we/e/1440, we/e/390 |
| SHELL (docs/js/app.js / ui.js) | mission | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 100 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | mission | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | mission | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | mission | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 90 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | network | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 221 not found | 2: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | network | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 177 not found | 2: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | network | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 331 not found | 2: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | network | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 338 not found | 2: we/e/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | network | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1240 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | network | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1356 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | network | key 7 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1495 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | network | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1335 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | network | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1382 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | network | 60-second tourS | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 443 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | network | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1329 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | network | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1196 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | network | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 323 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | network | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: console.error: unhandledrejection: Cannot read properties of null (reading 'getBoundingCli | 6: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | GROUNDED NO MORE — Mission Control | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Planner Action Centre8 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Parts Intelligence2 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Data & Method0 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Glossary | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Simple | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Keyboard shortcuts | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440, we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | GROUNDED NO MORE — Mission Control | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Planner Action Centre8 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Parts Intelligence2 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Data & Method0 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Glossary | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Page.click: Timeout 30000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Open navigation | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/390, ch/s/390, we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 3: ch/e/1440, ch/s/1440, we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 11 not found | 3: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 9 not found | 2: we/e/390, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 114 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | key 7 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 307 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | key 4 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 395 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 401 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | key 7 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 336 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 15 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 107 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 15 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: console.error: SyntaxError: The requested module './parts-intelligence/motion-helpers.js'  | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 106 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | GROUNDED NO MORE — Mission Control | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Mission Control1 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Planner Action Centre8 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | AOG Response Lab7 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Parts Intelligence2 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Rotable & Repair4 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Capital Optimiser6 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | 60-second tourS | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Data & Method0 | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | About | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Glossary | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | The Planner Behind the Project | link | navigates (route change / in-page anchor) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Open navigation | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Simulation W104–W155 | focusable | Enter on focusable has an effect | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | key ? | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 16 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc · pageerror: transition 10 not found | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | parts | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 104 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | Esc closes modal | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: ResizeObserver loop completed with undelivered notifications. | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | parts | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: ResizeObserver loop completed with undelivered notifications. | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | planner | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 3 not found | 4: we/e/1440, we/e/390, we/s/1440, we/s/390 |
| SHELL (docs/js/app.js / ui.js) | planner | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: console.error: unhandledrejection: Cannot read properties of null (reading 'getBoundingCli | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | planner | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 202 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | planner | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 1 not found | 1: ch/s/1440 |
| SHELL (docs/js/app.js / ui.js) | planner | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 74 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 27 not found | 5: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 53 not found | 2: we/e/1440, we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 361 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 412 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 7 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 420 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 474 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 0 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 382 not found | 1: ch/e/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 429 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 507 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 6 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 558 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 7 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 566 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 501 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 418 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 0 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 510 not found | 1: ch/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 5 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 488 not found | 1: ch/s/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc · pageerror: transition 21 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: focus lost to <body> after Esc | 1: we/s/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | Network Positioning5 | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 61 not found | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key s | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: no visible effect within 1 s | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 1 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: transition 7 not found | 1: we/e/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | Forecast Lab3 | link | navigates (route change / in-page anchor) | FAIL: pageerror: transition 69 not found | 1: we/e/390 |
| SHELL (docs/js/app.js / ui.js) | rotables | key 3 | shortcut | key action (route / help modal / tour; Esc closes) | FAIL: pageerror: ResizeObserver loop completed with undelivered notifications. | 1: we/s/1440 |
| SHELL (docs/js/app.js / ui.js) | rotables | Esc closes story | overlay-esc | Esc closes overlay, focus not on <body> | FAIL: pageerror: transition 21 not found | 1: we/s/390 |
| docs/js/views/about.js | about | What real data would make this useful | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 6: ch/e/1440, ch/e/390, ch/s/390, we/e/1440 |
| docs/js/views/aog-response-lab.js | aog | 05 AOG starts at T+0 h, BOM | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/1440, ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 06 Sourcing decided at T+0 h, AUH | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/1440, ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 07 Shipped at T+0 h, AUH | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/1440, ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 08 Arrived at T+9 h, BOM | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/1440, ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 09 Part at the aircraft at T+9 h, BOM | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/1440, ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 10 Fitted and released to service at T+14 h, BOM | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/1440, ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 02 Request at T+0 h, BOM | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 1: ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 03 Local stock check at T+0 h, BOM | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 1: ch/e/390 |
| docs/js/views/aog-response-lab.js | aog | 04 Network stock check at T+0 h, AUH | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 1: ch/e/390 |
| docs/js/views/data-method.js | method | Full entry | expander | <details> opens (View data) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 32: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | View data | expander | <details> opens (View data) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 16: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | Search assumptions | input | filter / result updates | FAIL: TimeoutError: Locator.fill: Timeout 30000ms exceeded. | 8: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | All | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | ● Real | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | ○ Assumed | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | ▲ Simulated | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | Filter by group | select | view re-renders for the option | FAIL: TimeoutError: Locator.select_option: Timeout 30000ms exceeded. | 8: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/data-method.js | method | More | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/390, we/e/390 |
| docs/js/views/forecast-lab.js | forecast | More | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 10: ch/e/390, ch/s/1440, ch/s/390, we/s/1440, we/s/390 |
| docs/js/views/glossary.js | glossary | Stock and network | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 3: ch/e/390, ch/s/390 |
| docs/js/views/glossary.js | glossary | Plans and money | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 3: ch/e/390, ch/s/390 |
| docs/js/views/glossary.js | glossary | Downtime and urgency | link | navigates (route change / in-page anchor) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: ch/e/390 |
| docs/js/views/mission-control.js | mission | Air conditioning & pressurisation. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 10: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390, we/e/390, we/s/1440 |
| docs/js/views/mission-control.js | mission | Air conditioning & pressurisation. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. · pageerror: transition 156 not found | 3: we/e/1440, we/s/1440, we/s/390 |
| docs/js/views/mission-control.js | mission | Landing gear: most urgent part GN-32-R014 at AUH. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 2: we/e/390, we/s/390 |
| docs/js/views/mission-control.js | mission | Airborne auxiliary power (APU). Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 148 not found | 2: we/e/1440, we/s/390 |
| docs/js/views/mission-control.js | mission | Pneumatic. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 154 not found | 1: ch/s/1440 |
| docs/js/views/mission-control.js | mission | Air conditioning & pressurisation. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. · pageerror: transition 157 not found | 1: we/e/1440 |
| docs/js/views/mission-control.js | mission | Pneumatic. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 146 not found | 1: we/s/1440 |
| docs/js/views/mission-control.js | mission | Pneumatic. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 91 not found | 1: we/e/390 |
| docs/js/views/mission-control.js | mission | Electrical power. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 97 not found | 1: we/e/390 |
| docs/js/views/mission-control.js | mission | Hydraulic power. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 99 not found | 1: we/e/390 |
| docs/js/views/mission-control.js | mission | Pneumatic. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 143 not found | 1: we/s/1440 |
| docs/js/views/mission-control.js | mission | Airborne auxiliary power (APU). Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 145 not found | 1: we/s/1440 |
| docs/js/views/mission-control.js | mission | Navigation. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 147 not found | 1: we/s/1440 |
| docs/js/views/mission-control.js | mission | Hydraulic power. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 151 not found | 1: we/s/1440 |
| docs/js/views/mission-control.js | mission | Navigation. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 150 not found | 1: we/s/390 |
| docs/js/views/mission-control.js | mission | Electrical power. Open Parts Intelligence | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: transition 152 not found | 1: we/s/390 |
| docs/js/views/network-positioning.js | network | AUH Abu Dhabi International: 146 Network Plan repairable units, material shortag | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 9: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390, we/s/1440 |
| docs/js/views/network-positioning.js | network | AUH · HIGH | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | LHR · ELEVATED | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | FRA · ELEVATED | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | CAI · HIGH | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | JED · HIGH | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | BOM · HIGH | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | SIN · ELEVATED | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 8: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/network-positioning.js | network | FRA Frankfurt am Main: 3 Network Plan repairable units, material shortage exposu | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 5: ch/e/1440, ch/s/1440, we/s/1440 |
| docs/js/views/network-positioning.js | network | Replay routine transfer of GN-21-C023 from AUH to BOM in W2 | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 5: ch/e/390, ch/s/390, we/s/390 |
| docs/js/views/network-positioning.js | network | Replay emergency transfer of GN-32-R014 from AUH to BOM in W2 | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/s/1440 |
| docs/js/views/parts-intelligence.js | parts | Narrowbody | toggle | state flips (aria-pressed/checked, re-render) | FAIL: pageerror: ResizeObserver loop completed with undelivered notifications. | 9: we/e/1440, we/e/390, we/s/1440, we/s/390 |
| docs/js/views/parts-intelligence.js | parts | All fleet | toggle | state flips (aria-pressed/checked, re-render) | FAIL: pageerror: ResizeObserver loop completed with undelivered notifications. | 9: we/e/1440, we/e/390, we/s/1440, we/s/390 |
| docs/js/views/parts-intelligence.js | parts | More | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 6: ch/s/390, we/s/390 |
| docs/js/views/parts-intelligence.js | parts | All 120 PNs | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/e/1440, ch/e/390, we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | All 120 parts | toggle | state flips (aria-pressed/checked, re-render) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 4: ch/s/1440, ch/s/390, we/s/1440, we/s/390 |
| docs/js/views/parts-intelligence.js | parts | Narrowbody | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | All fleet | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 34 Navigation: OK (system level OK). 11 part numbers, 0 urgent; top part GN- | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 24 Electrical power: OK (system level OK). 11 part numbers, 0 urgent; top pa | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 21 Air conditioning & pressurisation: OK (system level OK). 15 part numbers, | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 36 Pneumatic: OK (system level OK). 5 part numbers, 0 urgent; top part GN-36 | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 32 Landing gear: URGENT (system level Urgent). 20 part numbers, 6 urgent; to | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 29 Hydraulic power: OK (system level OK). 12 part numbers, 0 urgent; top par | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 27 Flight controls: URGENT (system level Urgent). 11 part numbers, 4 urgent; | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | ATA 49 Airborne auxiliary power (APU): OK (system level OK). 9 part numbers, 0 u | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 21Air conditioning & pressurisation15 PNs · top risk 1OK | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 24Electrical power11 PNs · top risk 1OK | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 27Flight controls11 PNs · top risk 81Urgent▲ 4 urgent PNs | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 29Hydraulic power12 PNs · top risk 46OK | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 32Landing gear20 PNs · top risk 100Urgent▲ 6 urgent PNs | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 34Navigation11 PNs · top risk 52OK | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 36Pneumatic5 PNs · top risk 0OK | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | 49Airborne auxiliary power (APU)9 PNs · top risk 0OK | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 3: we/e/1440, we/e/390 |
| docs/js/views/parts-intelligence.js | parts | Top-risk part in ATA 32: GN-32-R014, risk 100, Urgent. Open the part drill-down. | button | visible change (DOM / chart / modal / drawer) | FAIL: pageerror: Can't find variable: txSel | 1: we/s/390 |
| docs/js/views/parts-intelligence.js | parts | Widebody | toggle | state flips (aria-pressed/checked, re-render) | FAIL: console.error: unhandledrejection: tx is not a function. (In 'tx(ag.style('opacity', 0), { | 1: we/e/1440 |
| docs/js/views/parts-intelligence.js | parts | Widebody | toggle | state flips (aria-pressed/checked, re-render) | FAIL: pageerror: ResizeObserver loop completed with undelivered notifications. | 1: we/s/1440 |
| docs/js/views/parts-intelligence.js | parts?ata=32 | page load | load | route loads without console errors | FAIL: pageerror: Can't find variable: txSel; pageerror: Can't find variable: txSel · pageerror: Can't find variable: txSel | 1: we/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1650, serial GN-21-R026-S0003, AUH inhouse, open, overdue 26 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1784, serial GN-29-R012-S0010, AUH inhouse, open, overdue 5 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1605, serial GN-28-R010-S0074, EU vendor, open, overdue 12 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1612, serial GN-27-R009-S0016, EU vendor, open, overdue 23 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1625, serial GN-34-R018-S0121, EU vendor, open, overdue 29 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1635, serial GN-27-R009-S0041, EU vendor, open, overdue 12 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1638, serial GN-32-R013-S0014, EU vendor, open, overdue 2 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1639, serial GN-34-R039-S0005, EU vendor, open, overdue 18 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1642, serial GN-32-R036-S0037, EU vendor, open, overdue 3 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1648, serial GN-34-R018-S0081, EU vendor, open, overdue 17 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | RO-1668, serial GN-34-R018-S0149, EU vendor, open, overdue 9 d | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 7: ch/e/1440, ch/e/390, ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | More | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 6: ch/s/1440, we/s/1440 |
| docs/js/views/rotable-repair.js | rotables | Installed to Removed: 1,258 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | Installed to In repair: 477 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | Removed to In repair: 1,257 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to Installed: 11 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | In transit to Serviceable: 1,036 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | In transit to Installed: 292 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to Condemned: 62 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 4: ch/e/1440, ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to In transit: 1,130 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/e/1440, ch/s/1440 |
| docs/js/views/rotable-repair.js | rotables | On aircraft to Broken: 1,258 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | On aircraft to In repair: 477 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | Broken to In repair: 1,257 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to On aircraft: 11 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | In transit to Ready to fit: 1,036 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | In transit to On aircraft: 292 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to Scrapped: 62 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 3: ch/s/1440, ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | Serviceable to In transit: 201 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to Serviceable: 527 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/e/390 |
| docs/js/views/rotable-repair.js | rotables | Ready to fit to In transit: 201 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/s/390 |
| docs/js/views/rotable-repair.js | rotables | In repair to Ready to fit: 527 transitions | focusable | Enter on focusable has an effect | FAIL: no visible effect within 1 s | 2: ch/s/390 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 08 · Weather radar transceiver (GN-34-R020): comes off about 2 a year. Open part | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation | 1: ch/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 08 · Weather radar transceiver (GN-34-R020): comes off about 2 a year. Show deta | button | visible change (DOM / chart / modal / drawer) | FAIL: TimeoutError: Locator.click: Timeout 1000ms exceeded. | 1: ch/s/390 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 02 · Fuel boost pump (GN-28-R010): comes off about 13 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/vendor/fonts/inter/inter-lati | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 03 · Air cycle machine (GN-21-R002): comes off about 3 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/js/charts/theme.js cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 04 · Pack flow control valve (GN-21-R001): comes off about 11 a year. Open part  | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 05 · Brake control unit (GN-32-R017): comes off about 5 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 06 · Air data inertial reference unit (GN-34-R019): comes off about 36 a year. O | focusable | Enter on focusable has an effect | FAIL: requestfailed: http://127.0.0.1:49688/assets/svg/aircraft-narrowbody.svg cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 07 · Flight deck windshield (GN-30-E009): comes off about 5 a year. Open part pa | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/assets/svg/aircraft-narrowbod | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 08 · Nose wheel steering actuator (GN-32-R014): comes off about 27 a year. Open  | focusable | Enter on focusable has an effect | FAIL: requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 09 · Weather radar transceiver (GN-34-R020): comes off about 2 a year. Open part | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/demand_history.json canc | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 10 · Air data module (GN-34-R018): comes off about 89 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/demand_history.json canc | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 11 · Nose wheel and tyre assembly (GN-32-R016): comes off about 15 a year. Open  | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 12 · Elevator aileron computer (GN-27-R009): comes off about 15 a year. Open par | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/parts.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 13 · Pitot probe (GN-34-R021): comes off about 56 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · pageerror: /127.0.0.1:49688/data/parts.json due to access control c | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 14 · Transformer rectifier unit (GN-24-R005): comes off about 23 a year. Open pa | focusable | Enter on focusable has an effect | FAIL: requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 15 · Engine-driven hydraulic pump (GN-29-R011): comes off about 7 a year. Open p | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 16 · Integrated drive generator (GN-24-R004): comes off about 5 a year. Open par | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/assets/svg/aircraft-narrowbod | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 17 · Bleed air valve (GN-36-R022): comes off about 29 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 18 · Carbon brake assembly (GN-32-R013): comes off about 56 a year. Open part pa | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 21 · Spoiler servo control (GN-27-R008): comes off about 47 a year. Open part pa | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 22 · Aileron servo control (GN-27-R007): comes off about 9 a year. Open part pag | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/assets/svg/exploded-27.svg ca | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 23 · Flap position sensor (GN-27-E005): comes off about 21 a year. Open part pag | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/data/manifest.json cancelled | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 24 · APU fuel control unit (GN-49-R024): comes off about 11 a year. Open part pa | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/assets/svg/aircraft-narrowbod | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 25 · Elevator servo control (GN-27-R006): comes off about 16 a year. Open part p | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation | 1: we/s/1440 |
| docs/lab/cutaway.js (CUTAWAY) | lab/cutaway.html | 26 · APU starter motor (GN-49-R023): comes off about 3 a year. Open part page. | focusable | Enter on focusable has an effect | FAIL: Error: Page.evaluate: Execution context was destroyed, most likely because of a navigation · requestfailed: http://127.0.0.1:49688/assets/svg/aircraft-narrowbod | 1: we/s/1440 |

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
Pages: landing + the two heaviest workspaces by view JS + JSON bytes: **mission, rotables, network**.

| Page | preset | Performance | Accessibility | CLS | LCP ms | TBT ms |
|---|---|---:|---:|---:|---:|---:|
| mission | mobile | 73 | 100 | 0.192 | 4663 | 0 |
| mission | desktop | 93 | 100 | 0.095 | 1541 | 0 |
| rotables | mobile | 60 | 94 | 0.187 | 10057 | 0 |
| rotables | desktop | 90 | 94 | 0.095 | 1809 | 0 |
| network | mobile | 64 | 91 | 0.192 | 8860 | 0 |
| network | desktop | 91 | 95 | 0.095 | 1731 | 0 |

Accessibility audits not passing (any target page): Background and foreground colors do not have a sufficient contrast ratio.; Elements with visible text labels do not have matching accessible names.; Heading elements are not in a sequentially-descending order; Lists do not contain only `<li>` elements and script supporting elements (`<script>` and `<template>`).; Uses ARIA roles on incompatible elements; `[role]`s are not contained by their required parent element

**CLS on load** (layout-shift observer, 5 s, every route at 1440 and 390): max **0.1874**.
Worst: rotables@390 0.1874, mission@390 0.1873, parts@390 0.1873, forecast@390 0.1873, network@390 0.1873, capital@390 0.1873

**Animations** (rAF frame sampler + longtask observer; headless Chromium; ×4 = CDP CPU throttling):

| Scenario | fps | frame p50 / p95 / max ms | frames > 33 ms | long tasks > 50 / > 200 ms | longest task ms |
|---|---:|---|---:|---|---:|
| tour@x1 | 59.6 | 16.7 / 16.8 / 33.4 | 0 | 0 / 0 | 0 |
| slider@x1 | 59.7 | 16.7 / 16.8 / 16.8 | 0 | 0 / 0 | 0 |
| cutaway@x1 | 59.9 | 16.7 / 16.7 / 16.8 | 0 | 0 / 0 | 0 |
| tour@x4 | 58.7 | 16.7 / 16.8 / 133.3 | 7 | 3 / 0 | 109 |
| slider@x4 | 58.2 | 16.7 / 16.8 / 33.4 | 2 | 0 / 0 | 0 |
| cutaway@x4 | 59.6 | 16.7 / 16.7 / 16.8 | 0 | 0 / 0 | 0 |

Weights (view JS / JSON bytes): mission 34k/275k, parts 89k/167k, forecast 84k/413k, rotables 102k/500k, network 65k/520k, capital 86k/472k, aog 68k/195k, actions 54k/210k, method 50k/158k, about 16k/0k, glossary 7k/0k, planner 22k/0k

Verdicts:
```
{
 "lighthouse mission:mobile": {
  "performance>=85": false,
  "accessibility>=90": true,
  "cls<0.05": false
 },
 "lighthouse mission:desktop": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": false
 },
 "lighthouse rotables:mobile": {
  "performance>=85": false,
  "accessibility>=90": true,
  "cls<0.05": false
 },
 "lighthouse rotables:desktop": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": false
 },
 "lighthouse network:mobile": {
  "performance>=85": false,
  "accessibility>=90": true,
  "cls<0.05": false
 },
 "lighthouse network:desktop": {
  "performance>=85": true,
  "accessibility>=90": true,
  "cls<0.05": false
 },
 "cls_on_load<0.05 (all routes)": false,
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
