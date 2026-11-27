# Release gates — v2.2 "Final portfolio release"

Checked 2026-11-27 on `main` before tagging. Live site: https://akashgajjar07-hue.github.io/grounded-no-more/

| # | Gate | Result | Evidence |
|---|---|---|---|
| 1 | Frozen v2 holdout results unchanged (P0 ≈ 1,690 h · P1 ≈ 566 h · P2 ≈ 210 h · I125 ≈ 76 h) | ✅ | `gnm.freeze.verify()`: 19 hashed artefacts match `outputs/freeze/manifest.json` (re-checked on the final tree) |
| 2 | No re-tuning, new policies, calibration or simulations | ✅ | v2.2 changes are privacy cleanup, wording, display, site code, workbook cached values, and the brake-line sizing (read from the frozen plan) |
| 3 | Privacy: private material out of the public repo, site and history | ✅ | Moved to the private repo `grounded-no-more-private`. History rewritten with filter-repo after a backup bundle; tags re-created. GitHub repo size 510,036 KB → 25,573 KB. Live site: 0 hits on 53 page views (`reports/PUBLIC_SCAN.md`). Old commit SHAs may stay reachable on GitHub by ID until GitHub Support purges its cache |
| 4 | Forbidden-word gate | ✅ | `tests/test_public_scan.py` green. The last open repo hit (a DECISIONS.md wording) was fixed |
| 5 | Non-browser test suite | ✅ 398 / 398 | `pytest -m "not browser"` on the final tree |
| 6 | Browser tests | ✅ | 415 passed, 2 flaky on re-run (mission deep-link, network motion morph). After the parts badge fix: `tests/test_site_parts.py` 35 / 35 |
| 7 | CI + Pages | ✅ | GitHub Actions `CI` and Pages deployment green on the release commit |
| 8 | "Every button works" audit | ⚠️ partial, 0 failed | 91 cells, 6,312 controls, 6,072 ok, 0 failed, 240 skipped (Chromium 68 cells, WebKit 23). Stopped at the time limit; unfinished cells are listed as "not completed — time limit" in `reports/INTERACTION_AUDIT.md` §1b. The audit found one real bug, a dead click gap on parts ATA badges. It was fixed in ede9626 and verified by tests and a targeted Chromium/WebKit check at 1440 and 390 |
| 9 | Firefox | ⚠️ not run | Local launch failure ("Could not find profile folder"; V21-FF) |
| 10 | Every link works every time | ✅ | 6,450 internal link clicks, 0 failed; external 46 / 46 return 200; 51 / 51 relative repo links tracked (`reports/LINK_CHECK.md`) |
| 11 | Tour: frame/video check | ✅ checker · ⚠️ critic | Frame checks pass in Chromium and WebKit at 1440 and 390: step change ≤ 1.2 s, 58–60 fps, CLS 0, spotlight still while the card shows, card text fits (`reports/tour/frame_check.json`). Fresh critic (smoothness / polish): 3.5/3.5 → 4.0/3.5 → 3.9/3.6, below the 4.5 bar; the time limit was reached |
| 12 | Simple / Expert differ on every page, or say they read the same | ✅ | Every page differs except Planner, which carries the "reads the same" note; About was changed in v2.2. Readability grade ≤ 9 and no sentence > 25 words (`reports/readability/`) |
| 13 | Lighthouse ≥ 85 perf / ≥ 90 a11y (live) | ✅ | Landing: mobile 88 / 100, desktop 100 / 100. Capital: mobile 91 / 96, desktop 99 / 95 (`reports/perf/lighthouse_release.json`) |
| 14 | CLS < 0.05 and ~60 fps | ✅ | Live CLS on load max 0.028 across 26 route × width checks; tour 58–60 fps, 0 frames > 34 ms |
| 15 | Workbook cached values | ✅ | 3,031 formula cells carry cached values. openpyxl `data_only=True` reads no empty and no error cells. Workbook tests and number reconciliation green |
| 16 | No dangling commit hashes | ✅ | Every commit hash cited in tracked Markdown and report JSON resolves to a commit on `main` (pre-rewrite hashes mapped or replaced by the release tag) |
| 17 | Flagged outstation brake lines sized | ✅ | Network Plan: 5 lines, 5 units, ≈ AED 0.99M (0.05 % of target units, 3.1 % of target stock value). Shown beside the flag on the site and in LIMITATIONS, read from the frozen plan |
| 18 | Live smoke, Chromium + WebKit | ✅ | Landing, tour steps 1–6 and close, section deep link, Results scope line, workbook download, cutaway; no page errors (`reports/audit/live_smoke.json`) |
| 19 | Final screenshots | ✅ | 25 compressed JPEGs from the live site (12 workspaces × Simple/Expert + cutaway), 3.4 MB, `reports/final_screens/` |
| 20 | Nothing posted anywhere | ✅ | No social-media or public posting |
