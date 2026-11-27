# Link check (v2.2)

## External links (DOCS)

Checked on 2026-11-27 with `curl -L`: a generic user agent, HEAD first with a 1-byte ranged GET as fallback, at most 4 requests in parallel, and up to 4 attempts on 429, 5xx or timeouts. Nothing was downloaded or saved.

**Scope.** Every `http(s)` URL found in these places:
- the site: `docs/index.html`, `docs/js`, `docs/content`, `docs/data`, `docs/lab`;
- the doc templates and the rendered docs: README, METHODOLOGY, MODEL_CARD, LIMITATIONS, reports/VALIDATION_REPORT.md, THIRD_PARTY_LICENSES, docs/*.md, data/data_dictionary.md, archive/v1/README.md;
- the deck (PPTX text and hyperlinks) and the workbook (cell text and hyperlinks).

Some GitHub links are built at run time. These were resolved by hand and checked as GitHub URLs: the Planner page's project documents (`planner.js` DOCS), Mission Control's Limitations link, and the About page's content links (the content files only link to each other). Every relative repo link in the Markdown docs was checked the same way, because GitHub serves it as `blob/main/…`. `http://www.w3.org/2000/svg` is an XML namespace, not a link, so it is excluded.

**Result: 46 of 46 unique URLs return 200. None returns 404 or any other error.** Every relative repo link (51 of 51) points at a file tracked in git.

**Fixed in this run.**
- METHODOLOGY linked a file that was moved out of the public repo, which is a 404 on GitHub. That sentence now points to the planner workbook (`docs/templates/METHODOLOGY.md.tmpl`), and METHODOLOGY.md was re-rendered.
- No GitHub link to a file moved out of the public repo is left in the site, the docs, the deck or the workbook.

**Caveats.**
- GitHub links were checked against the current `main` on GitHub. That matches the working tree except for the METHODOLOGY fix above, which goes live when the lead pushes.
- `reports/audit/links_downloads.json` (ROUTER) still lists a file moved out of the public repo. It is an audit artefact, not a page link. It is in the ROUTER requests in reports/PUBLIC_SCAN.md.
- LIMITATIONS and reports/VALIDATION_REPORT.md link the AI review records (`reports/review_*.md`). If the lead moves those records out of the public repo, the links in the templates have to go first (DOCS).

| Status | URL | Found in |
|---|---|---|
| 200 | https://akashgajjar07-hue.github.io/grounded-no-more/ | README.md:11, deck slide 1 (bare), deck slide 10 (bare) (+2 more) |
| 200 | https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.1.0/files/ | THIRD_PARTY_LICENSES.md:15 |
| 200 | https://cdn.jsdelivr.net/npm/@fontsource/inter@5.1.0/files/ | THIRD_PARTY_LICENSES.md:14 |
| 200 | https://cdn.jsdelivr.net/npm/@fontsource/space-grotesk@5.1.0/files/ | THIRD_PARTY_LICENSES.md:13 |
| 200 | https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/dist/plot.umd.min.js | THIRD_PARTY_LICENSES.md:10 |
| 200 | https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js | THIRD_PARTY_LICENSES.md:9 |
| 200 | https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js | THIRD_PARTY_LICENSES.md:11 |
| 200 | https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/ | THIRD_PARTY_LICENSES.md:12 |
| 200 | https://creativecommons.org/licenses/by/4.0/ | docs/data/forecast.json:1 |
| 200 | https://davidmegginson.github.io/ourairports-data/airports.csv | docs/data/method.json:1 |
| 200 | https://forecastingdata.org/ | docs/data/forecast.json:1 |
| 200 | https://github.com/akashgajjar07-hue | README.md:320, deck slide 10 (bare), docs/js/views/about.js:22 (+2 more) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more | deck slide 1 (bare), deck slide 10 (bare), docs/js/views/about.js:24 (+1 more) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more.git | README.md:268, docs/templates/README.md.tmpl:245 |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/actions/workflows/ci.yml | README.md:7, docs/templates/README.md.tmpl:7 |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/actions/workflows/ci.yml/badge.svg | README.md:7, docs/templates/README.md.tmpl:7 |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/LIMITATIONS.md | METHODOLOGY.md:79 (relative), MODEL_CARD.md:3 (relative), README.md:129 (relative) (+7 more) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/METHODOLOGY.md | LIMITATIONS.md:39 (relative), MODEL_CARD.md:3 (relative), README.md:236 (relative) (+1 more) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/MODEL_CARD.md | README.md:236 (relative), docs/js/views/planner.js DOCS |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/THIRD_PARTY_LICENSES.md | README.md:326 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/archive/v1/README.md | LIMITATIONS.md:11 (relative), METHODOLOGY.md:5 (relative), MODEL_CARD.md:5 (relative) (+2 more) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/config/assumptions.yaml | METHODOLOGY.md:3 (relative), docs/assumption_register.md:5 (relative), docs/data_contract.md:6 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/config/part_catalogue.csv | METHODOLOGY.md:3 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/data/data_dictionary.md | README.md:253 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/docs/DECISIONS.md | METHODOLOGY.md:33 (relative), METHODOLOGY.md:34 (relative), METHODOLOGY.md:415 (relative) (+4 more) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/docs/assets/readme/hero.png | README.md:13 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/docs/assets/readme/pipeline.svg | README.md:227 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/docs/assumption_register.md | LIMITATIONS.md:11 (relative), METHODOLOGY.md:3 (relative), README.md:253 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/docs/data_contract.md | METHODOLOGY.md:3 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/excel/grounded_no_more_planner_workbook.xlsx | METHODOLOGY.md:271 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/VALIDATION_REPORT.md | README.md:236 (relative), docs/js/views/planner.js DOCS |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_aviation.md | reports/VALIDATION_REPORT.md:239 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_aviation_v2.md | LIMITATIONS.md:117 (relative), reports/VALIDATION_REPORT.md:240 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_correctness.md | reports/VALIDATION_REPORT.md:241 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_design.md | reports/VALIDATION_REPORT.md:242 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_design_2.md | reports/VALIDATION_REPORT.md:243 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_design_3.md | reports/VALIDATION_REPORT.md:244 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_design_4.md | reports/VALIDATION_REPORT.md:245 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/reports/review_design_5.md | reports/VALIDATION_REPORT.md:246 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/src/gnm/contracts.py | docs/data_contract.md:5 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/blob/main/src/gnm/schemas.py | data/data_dictionary.md:5 (relative), docs/data_contract.md:4 (relative) |
| 200 | https://github.com/akashgajjar07-hue/grounded-no-more/tree/main/LICENSE | README.md:326 (relative), README.md:9 (relative) |
| 200 | https://img.shields.io/badge/licence-MIT-B9C8D6 | README.md:9, docs/templates/README.md.tmpl:9 |
| 200 | https://img.shields.io/badge/python-3.11%2B-22C7B8 | README.md:8, docs/templates/README.md.tmpl:8 |
| 200 | https://zenodo.org/records/4656021 | docs/data/forecast.json:1, docs/data/method.json:1 |
| 200 | https://zenodo.org/records/4656021/files/car_parts_dataset_without_missing_values.zip | docs/data/method.json:1 |

## Internal links (ROUTER)

*Written by ROUTER.*

<!-- internal:start (written by tests/e2e/test_links_every_time.py) -->
Generated 2026-11-27 17:12 by `tests/e2e/test_links_every_time.py` (chromium, webkit, 1440 x 900, Simple mode).

Every internal link found on every route (`a[href^="#/"]` in the shell and the page, plus in-page anchors such as the
skip link; the glossary group chips are `?section=` links) was clicked 5 times from each of 3 starting states (fresh load, coming from
another page, already on the target URL), returning with browser Back between clicks that left the page. After every
click: the URL equals the link, the target route rendered, and for section links the target heading is in the
viewport and focused. Links to the current route have no skip allowance.

**Totals: 1254 link checks, 6270 clicks, 0 failed.**

| Browser | Route | Links | Clicks | Failed | Seconds |
|---|---|---:|---:|---:|---:|
| chromium | about | 60 | 300 | 0 | 170.2 |
| chromium | actions | 42 | 210 | 0 | 170.4 |
| chromium | aog | 42 | 210 | 0 | 172.4 |
| chromium | capital | 42 | 210 | 0 | 172.1 |
| chromium | forecast | 78 | 390 | 0 | 322.0 |
| chromium | glossary | 63 | 315 | 0 | 160.0 |
| chromium | method | 48 | 240 | 0 | 154.7 |
| chromium | mission | 72 | 360 | 0 | 290.5 |
| chromium | network | 42 | 210 | 0 | 173.1 |
| chromium | parts | 45 | 225 | 0 | 184.5 |
| chromium | planner | 51 | 255 | 0 | 50.4 |
| chromium | rotables | 42 | 210 | 0 | 173.3 |
| webkit | about | 60 | 300 | 0 | 202.2 |
| webkit | actions | 42 | 210 | 0 | 178.0 |
| webkit | aog | 42 | 210 | 0 | 174.8 |
| webkit | capital | 42 | 210 | 0 | 179.5 |
| webkit | forecast | 78 | 390 | 0 | 159.6 |
| webkit | glossary | 63 | 315 | 0 | 153.2 |
| webkit | method | 48 | 240 | 0 | 178.6 |
| webkit | mission | 72 | 360 | 0 | 160.7 |
| webkit | network | 42 | 210 | 0 | 177.6 |
| webkit | parts | 45 | 225 | 0 | 185.5 |
| webkit | planner | 51 | 255 | 0 | 53.8 |
| webkit | rotables | 42 | 210 | 0 | 186.9 |

No failures.

<!-- internal:end -->
