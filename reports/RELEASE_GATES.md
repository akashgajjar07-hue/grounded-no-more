# Release gates — v2.1 "Final portfolio release"

Checked 2026-11-27 on `main` before tagging. Live site: https://akashgajjar07-hue.github.io/grounded-no-more/

| # | Gate | Result | Evidence |
|---|---|---|---|
| 1 | Frozen v2 holdout results unchanged (P0 ≈ 1,690 h · P1 ≈ 566 h · P2 ≈ 210 h · I125 ≈ 76 h) | ✅ | `gnm.freeze.verify()`: 19 hashed artefacts match `outputs/freeze/manifest.json` |
| 2 | No re-tuning, new policies, calibration or simulations | ✅ | v2.1 changes are wording, display, post-processing (donor recount, labelled post-plan) and site code only |
| 3 | Non-browser test suite | ✅ 394 / 394 | `pytest -m "not browser"` |
| 4 | Browser tests | ✅ | Full browser suite green before the final tour/router changes; afterwards every touched file re-run green (260 + 101 passed, 1 skipped). 1,071 tests collected in total, including 319 audit cells |
| 5 | CI | ✅ | GitHub Actions `CI` green on the release commit |
| 6 | "Every button works" audit | ✅ 0 failed · 0 disabled | 162 cells · 12,853 controls · 12,228 ok · 625 skipped (re-rendered / same-route no-ops). Chromium: all 27 targets × Simple/Expert × 1440/390. WebKit: all targets × Simple/Expert at 1440, plus a 390 smoke. `reports/INTERACTION_AUDIT.md` |
| 7 | Firefox | ⚠️ not run | "Firefox not run — local launch failure" (Playwright Firefox: "Could not find profile folder"; V21-FF) |
| 8 | Lighthouse ≥ 85 perf / ≥ 90 a11y (live) | ✅ | Landing: mobile 89 / 100, desktop 100 / 100. Capital: mobile 91 / 96, desktop 99 / 95. `reports/perf/lighthouse_release.json` |
| 9 | CLS < 0.05 | ✅ | Max 0.028 across all routes on load (live); tour run 0.001 |
| 10 | No long task > 200 ms, ~60 fps | ✅ | Tour 59.9 fps, 3 of 3,342 frames > 20 ms, longest task 39.8 ms (`reports/perf/tour_trace.json`). Slider and cutaway 58–60 fps |
| 11 | Grep gate (forbidden words, OEM / airline names) on product surfaces | ✅ 0 hits | Site, docs, README, study pack, deck. The only workbook hits are a row number and a numeric cell value |
| 12 | Scope line on every headline KPI | ✅ | Verified live on Results (smoke) and in the tests |
| 13 | Simple / Expert readability (grade ≤ 9, no sentence > 25 words) | ✅ | Grades 3.1–6.1 across 12 pages (`reports/readability/`) |
| 14 | Cutaway hero rule (hero only if mean ≥ 4.3) | ✅ applied | 4 rounds: 3.0 → 3.4 → 3.70 → 3.60, so it went to the Explore section and the hero is unchanged (V21-D2) |
| 15 | Live smoke, Chromium + WebKit | ✅ | Landing, tour Play (auto-advances), Results (scope line + capital note), Explore link, workbook download, cutaway. No console errors. `reports/audit/live_smoke.json` |
| 16 | Final screenshots | ✅ | 25 compressed JPEGs from the live site (12 workspaces × Simple/Expert + cutaway), 3.3 MB, `reports/final_screens/` |
| 17 | Repo hygiene | ✅ | No traces, videos, HTML reports or bulk audit cells tracked. Tracked tree 24 MB (docs/ 8.4 MB). History not rewritten (V21-R), so GitHub reports ≈ 495 MB |
| 18 | Nothing posted anywhere | ✅ | LinkedIn post and carousel remain drafts in `presentations/` |
