# Public scan (v2.2)

A full scan of the public repo for private, placeholder and forbidden wording, before and after the v2.2 fixes. DOCS fixed the hits in its own files. Hits in other owners' files are routed below with the exact replacement.

## Method

- **Files.** Every file in `git ls-files` that holds text (.md, .js, .mjs, .json, .py, .css, .html, .csv, .yaml, .tmpl, .sql, .ipynb, .xml, .svg, .txt, .toml). The scan also reads the text inside the binary downloads:
  - `presentations/case_study_deck.pptx`: slide text, tables and notes;
  - `presentations/case_study_deck.pdf` and `docs/downloads/case_study_deck.pdf`: the PDF text layer, read with macOS PDFKit;
  - `excel/` and `docs/downloads/` workbook: every string cell and comment.
- **Terms** (case-insensitive unless shown in capitals):
  - interview, LinkedIn, recruiter, `CEO`, hire/hiring, job(s) as a word, girlfriend, prompt, subagent, agent notes, "Claude Code prompt", `TODO`, `FIXME`, `TBD`, "add link", lorem, placeholder, `DRAFT`;
  - Etihad, Airbus, Boeing, A320, 787 as a type designation (numbers such as `787.54` or SVG path coordinates do not count);
  - legacy.
- **Counting.** One hit is one line matching one term. The tables group hits by file and term.
- **Judgement.**
  - Only user-visible text and docs count. Code identifiers, code comments, test code, an HTML `placeholder` attribute and a CSS `::placeholder` selector are exempt.
  - The frozen config (`config/*.yaml`), frozen outputs and the frozen simulator code are exempt because they cannot be edited.
  - The README keeps one neutral sector line, under *Context*: "Relevant to Abu Dhabi hub carriers and MRO organisations; independent project, not affiliated with any airline." It names no airline, manufacturer or type, so it stays.

## Totals

| | Hits | Fixed | Exempt | Routed | Regenerated |
|---|---|---|---|---|---|
| First scan | 298 | 63 | 134 | 100 | 1 |
| Re-run after the fixes | 257 | 0 left | 149 | 108 (still open, owners below) | 0 |

The re-run total is not the first total minus the fixes. Counts are per line and per term, other agents edited files during this run (ROUTER and PAGES fixed their own hits), and the review records gained lines.

**What DOCS fixed:**
- Every "legacy" in the doc templates, the rendered docs, `scripts/render_docs.py` text, the site export text fields (`src/gnm/export`, `docs/data/kpis.json`, `docs/data/method.json`) and the deck and workbook. The frozen config and outputs still say "legacy", so a relabel pass now catches that wording on the way out: `v21.scrub` for docs/data and `render_docs.relabel` for the docs.
- The social-media carousel and post generator: it moved from the public `scripts/build_deck.py` to the git-ignored `private/scripts/build_social.py`. The public deck script no longer contains LinkedIn or DRAFT text.
- The METHODOLOGY link to the removed study guide.
- "result placeholder" in VALIDATION_REPORT, reworded.
- "hiring manager" in `notebooks/01_simulation_audit.ipynb`.
- `reports/junit.xml`, regenerated: the old run showed 1 failure.

## Routed (exact replacements)

**ROUTER**
- `docs/js/views/rotable-repair.js`, Simple-mode copy ("job" as a word):
  - :131: `byMode('Open repair jobs', …)` → `byMode('Open repairs', …)`, and `unit: byMode('jobs', 'ROs')` → `unit: byMode('repairs', 'ROs')`;
  - :132: `'Repair jobs past due'` → `'Repairs past due'`, `unit: byMode('jobs', 'ROs')` → `byMode('repairs', 'ROs')`, and `byMode('job', 'RO')` → `byMode('repair', 'RO')`;
  - :185: `byMode('Repair jobs', 'Repair orders')` → `byMode('Repairs', 'Repair orders')`, and `open repair jobs, latest first` → `open repairs, latest first`;
  - :190: `byMode('Job', 'RO')` → `byMode('Repair', 'RO')`;
  - :352: `Every open repair job is still inside its promised date` → `Every open repair is still inside its promised date`, and `repair jobs are past their promised date` → `repairs are past their promised date`;
  - :456: `isSimple() ? 'job' : 'RO'` → `isSimple() ? 'repair' : 'RO'`;
  - :521: `${fmtInt(d.n)} jobs` → `${fmtInt(d.n)} repairs`.
  - Then remove the matching `PENDING` entries in `tests/test_public_scan.py`. The test warns when an entry is no longer needed.
- `reports/audit/links_downloads.json` :828, :831 still list a removed study-pack file, and `reports/audit/numbers_reconcile.json` :157 still lists `presentations/linkedin_post.md`. Regenerate both, or put a top-level `"status": "interim baseline (superseded)"`.
- `reports/audit/keyboard/rotables.json` :255, :266 record the control label "Job". Regenerate it after the rotable-repair fix.

**Lead**
- `docs/assets/readme/pipeline.svg` :58 (README image): `104 weeks under legacy` → `104 weeks under P0 rules`.
- `docs/assets/svg/src/aircraft-plan.mjs` :236 → `(single-aisle proportions)` in place of `(A320-family proportions)`, and :265 → `(twin-aisle proportions)` in place of `(787-family proportions)`. Apply the same change to the comments at :2–3. Then regenerate `aircraft-narrowbody.svg` and `aircraft-widebody.svg` (line 3 `<desc>`, read by screen readers).
- `docs/assumption_register.md` :414, :426, :479: add these pairs to `RELABEL` in `scripts/render_data_dictionary.py`, then re-run it: `("Legacy OEM-quote", "Starting-point OEM-quote")`, `("legacy OEM-quote", "starting-point OEM-quote")`, `("legacy line-station", "starting-point line-station")`, `("legacy provisioning", "starting-point provisioning")`.
- `scripts/notebooks/nb01.py` :9: `A hiring manager, or a sceptical materials planner, should` → `A sceptical materials planner or reviewer should`. The notebook already says this, and the change keeps the generator in step.
- `docs/design/DESIGN_SYSTEM.md` :211 and `docs/design/gallery.js` :86: `versus legacy rules` → `versus the Simple Rulebook`. Also `gallery.js` :134: the demo state label "placeholder" → "reserved".
- `archive/v1/README.md` :12: `P0 legacy (stock to pipeline mean)` → `P0 Simple Rulebook (stock to pipeline mean)`; :18: `A320- and 787-family archetypes` → `narrowbody and widebody archetypes`.
- `docs/DECISIONS.md`:
  - :13: `P0 "legacy" rules` → `P0 Simple Rulebook rules`;
  - :32: `P0 'legacy' rule` → `P0 Simple Rulebook rule`;
  - :44: `static legacy rules` → `static starting-point rules`;
  - :88: `legacy OEM-quote provisioning` → `starting-point OEM-quote provisioning`;
  - :16: `placeholders` → `result keys`;
  - :18: `to avoid an off-by-one in interviews` → `to avoid an off-by-one`;
  - :117: drop `, the study guide's evaluation line, interview Q3`;
  - :73: `787-family archetype` → `widebody archetype`;
  - :112: `"A320-family / 787-family archetype" labels` → `OEM-family archetype labels`, and drop `study pack,` and `video script` from the surface list.
- `reports/RELEASE_GATES.md` :24: "LinkedIn post and carousel remain drafts in `presentations/`" → `Social-media drafts are kept outside the public repo and were not posted`.
- **AI review records** (`reports/review_aviation.md`, `review_aviation_v2.md`, `review_correctness.md`, `review_design.md`, `review_design_2.md`, `review_design_3.md`, `review_design_5.md`, `reports/cutaway_critique_r1.md`, `cutaway_critique_r2.md`, `docs/design-review/REVIEW_LOG.md`). Their reviewer framing names a hiring panel, a hiring manager, a recruiter and interviews. They quote "LinkedIn: add link" and use "legacy", "A320", "787", "Airbus" and "Boeing". Recommendation: move them to the private repo. LIMITATIONS and VALIDATION_REPORT link them, so tell DOCS first and the links will be removed. The alternative is to reword the framing lines: review_aviation.md :5, :9, :57; review_aviation_v2.md :5, :87; review_design.md :112, :253; review_design_3.md :42, :244; review_design_5.md :190, :309; review_correctness.md :91; review_design_2.md :33, :128, :153, :189; REVIEW_LOG.md :207. The file:line list is in the tables below.

## First scan, every hit

| File | Lines | Term | Action |
|---|---|---|---|
| `.github/workflows/ci.yml` | 6 | job | exempt: YAML key `jobs:` |
| `.gitignore` | 40 | agent notes | exempt: ignore rules that keep the private paths out of git |
| `.gitignore` | 41 | LinkedIn | exempt: ignore rules that keep the private paths out of git |
| `LIMITATIONS.md` | 29, 39, 122 | legacy | fixed (DOCS) |
| `METHODOLOGY.md` | 57, 144, 155, 163, 425 | legacy | fixed (DOCS) |
| `README.md` | 152 | legacy | fixed (DOCS) |
| `archive/v1/README.md` | 12 | legacy | routed: lead |
| `archive/v1/README.md` | 18 | 787 | routed: lead |
| `archive/v1/README.md` | 18 | A320 | routed: lead |
| `config/assumptions.yaml` | 41, 354 | A320 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | 49, 354 | 787 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | 221, 319, 321 | legacy | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | 229 | agent notes | exempt: frozen config (cannot be edited) |
| `config/optimiser.yaml` | 4 | agent notes | exempt: frozen config (cannot be edited) |
| `data/ground_truth/planted.json` | 6 | legacy | exempt: frozen artefact / frozen simulator code |
| `docs/DECISIONS.md` | 13, 32, 44, 88 | legacy | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 16 | placeholder | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 18, 117 | interview | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 112 | A320 | routed: lead (DECISIONS.md is lead-written) |
| `docs/assets/readme/pipeline.svg` | 58 | legacy | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/aircraft-narrowbody.svg` | 3 | A320 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/src/aircraft-plan.mjs` | 2, 236 | A320 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/src/aircraft-plan.mjs` | 3, 265 | 787 | routed: lead (unowned assets; aria text and README image) |
| `docs/assumption_register.md` | 414, 426, 479 | legacy | routed: lead (generator scripts/render_data_dictionary.py, relabel table) |
| `docs/css/components.css` | 510 | placeholder | exempt: CSS comment or `::placeholder` selector |
| `docs/css/motion.css` | 15 | legacy | exempt: CSS comment or `::placeholder` selector |
| `docs/css/views/data-method.css` | 29 | placeholder | exempt: CSS comment or `::placeholder` selector |
| `docs/data/kpis.json` | 1 | legacy | fixed (DOCS) |
| `docs/data/method.json` | 1 | legacy | fixed (DOCS) |
| `docs/design-review/REVIEW_LOG.md` | 11, 67 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | 179 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | 207 | LinkedIn | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | 207 | add link | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design/DESIGN_SYSTEM.md` | 211 | legacy | routed: lead (design-system gallery sample copy) |
| `docs/design/gallery.js` | 86 | legacy | routed: lead (design-system gallery sample copy) |
| `docs/design/gallery.js` | 134 | placeholder | routed: lead (design-system gallery sample copy) |
| `docs/js/charts/theme.js` | 393 | legacy | exempt: code comment |
| `docs/js/ui.js` | 1228 | placeholder | exempt: code comment |
| `docs/js/views/capital-optimiser.js` | 626 | legacy | fixed by ROUTER during this run |
| `docs/js/views/data-method.js` | 36, 335, 336 | LinkedIn | fixed by PAGES during this run (LinkedIn chip and comment removed) |
| `docs/js/views/data-method.js` | 314 | placeholder | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/data-method.js` | 335 | placeholder | fixed by PAGES during this run (LinkedIn chip and comment removed) |
| `docs/js/views/glossary.js` | 50 | placeholder | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/network-positioning.js` | 119, 228 | legacy | exempt: code comment |
| `docs/js/views/network-positioning.js` | 685, 686 | legacy | fixed by ROUTER during this run |
| `docs/js/views/parts-intelligence.js` | 222 | placeholder | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/planner.js` | 3, 38, 53 | DRAFT | fixed by PAGES during this run (DRAFT badge removed) |
| `docs/js/views/rotable-repair.js` | 131, 132, 185, 190, 352, 456, 521 | job | routed: ROUTER (Simple-mode copy says 'repair job(s)') |
| `docs/templates/LIMITATIONS.md.tmpl` | 29, 33, 116 | legacy | fixed (DOCS) |
| `docs/templates/METHODOLOGY.md.tmpl` | 57, 139, 145, 354 | legacy | fixed (DOCS) |
| `docs/templates/README.md.tmpl` | 133 | legacy | fixed (DOCS) |
| `docs/templates/VALIDATION_REPORT.md.tmpl` | 15 | placeholder | fixed (DOCS) |
| `docs/templates/VALIDATION_REPORT.md.tmpl` | 115 | legacy | fixed (DOCS) |
| `notebooks/01_simulation_audit.ipynb` | 12 | hire/hiring | fixed (DOCS): 'A hiring manager, or…' reworded |
| `notebooks/01_simulation_audit.ipynb` | 1030, 1069 | legacy | exempt: recorded cell output printing a frozen artefact's variant key |
| `outputs/calibration/v2_p0_gap_diagnosis.json` | 5475 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | 67, 124, 153, 263, 309, 345 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | 139 | A320 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_variants.json` | 270 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/holdout/truth_recovery.json` | 44 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/policies/tuning_v1/iter0_policies.json` | 7 | legacy | exempt: frozen artefact / frozen simulator code |
| `reports/RELEASE_GATES.md` | 24 | LinkedIn | routed: lead (stale claim: the drafts are no longer in presentations/) |
| `reports/VALIDATION_REPORT.md` | 26 | placeholder | fixed (DOCS) |
| `reports/VALIDATION_REPORT.md` | 43, 49, 82, 131, 138, 219, 225 | legacy | fixed (DOCS) |
| `reports/audit/keyboard/rotables.json` | 255, 266 | job | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/audit/links_downloads.json` | 828, 831 | interview | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/audit/numbers_reconcile.json` | 157 | LinkedIn | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/cutaway_critique_r1.md` | 39 | A320 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r1.md` | 39 | Airbus | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r1.md` | 39 | Boeing | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r2.md` | 49 | Airbus | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r2.md` | 49 | Boeing | routed: lead (AI review records; move to the private repo or reword) |
| `reports/junit.xml` | 1 | placeholder | regenerated (old run with 1 failure replaced) |
| `reports/review_aviation.md` | 5 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 9, 29, 57 | interview | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 17, 19, 31 | A320 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 18, 19, 23, 40 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 29 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 5 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 16, 28, 37 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 30, 39, 46, 47, 77 | A320 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 39, 41, 46, 77 | 787 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 42 | job | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 87 | interview | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | 20, 21, 26, 39, 84 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | 36 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | 91 | interview | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design.md` | 112, 253 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design.md` | 211 | job | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 33, 128, 153, 189 | LinkedIn | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 33, 128, 153 | add link | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 71, 201 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 128, 153 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | 42 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | 42 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | 244 | recruiter | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_5.md` | 190, 309 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `scripts/build_deck.py` | 2, 1776, 1789, 1938, 1954, 1956, 1959, 2107, 2109 | DRAFT | fixed (DOCS): carousel and post generator moved to private/scripts/build_social.py (git-ignored) |
| `scripts/build_deck.py` | 2, 1937, 1956, 1959, 2105, 2107, 2108, 2109 | LinkedIn | fixed (DOCS): carousel and post generator moved to private/scripts/build_social.py (git-ignored) |
| `scripts/build_deck.py` | 746, 757 | job | exempt: local variable `jobs` |
| `scripts/build_deck.py` | 2015 | legacy | exempt: stale-label gate list in code |
| `scripts/dev/make_fixtures.mjs` | 3, 29, 112, 119, 131, 135, 151, 164, 182, 191, 217, 221, 228, 234 | placeholder | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/dev/make_fixtures.mjs` | 114 | legacy | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/notebooks/nb01.py` | 9 | hire/hiring | routed: lead (notebook generator; the notebook itself is fixed) |
| `scripts/render_data_dictionary.py` | 23, 24 | 787 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_data_dictionary.py` | 23, 24 | A320 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_docs.py` | 3, 12, 51, 1381, 1384, 1388 | placeholder | exempt: code identifier (`PLACEHOLDER` regex) and docstring |
| `scripts/render_docs.py` | 346, 512, 530, 768 | legacy | fixed (DOCS) |
| `scripts/render_docs.py` | 710 | legacy | exempt: relabel table / code comment |
| `scripts/render_docs.py` | 997, 998, 999, 1000 | 787 | exempt: relabel table / code comment |
| `scripts/render_docs.py` | 997, 998, 999, 1000 | A320 | exempt: relabel table / code comment |
| `scripts/v2_p0_variants_measure.py` | 4, 60 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/01_top_aog_drivers.sql` | 4 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/05_lead_time_drift.sql` | 8 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/07_d0_outstation_no_stock.sql` | 3, 9 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/run_all.py` | 9 | legacy | exempt: code comment / docstring (not a product surface) |
| `src/gnm/eval/truth_recovery.py` | 4 | legacy | exempt: code comment / docstring (not a product surface) |
| `src/gnm/export/build_site_data.py` | 194 | legacy | exempt: code comment |
| `src/gnm/export/build_site_data.py` | 498, 678 | legacy | fixed (DOCS) |
| `src/gnm/export/v21.py` | 138 | legacy | exempt: scrub/gate patterns that remove these words |
| `src/gnm/policy/evaluate_policies.py` | 7 | legacy | exempt: code comment / docstring (not a product surface) |
| `src/gnm/sim/engine.py` | 1372, 1373, 1376, 1380 | job | exempt: frozen artefact / frozen simulator code |
| `src/gnm/sim/generator.py` | 359 | legacy | exempt: frozen artefact / frozen simulator code |
| `tests/test_docs_rendered.py` | 1, 45 | placeholder | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 26 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 27 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 27 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 28 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 28 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 320 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 330 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 15 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_data.py` | 256, 258, 262 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_data.py` | 257, 258 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | 32 | LinkedIn | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | 32 | placeholder | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | 33 | add link | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | 1, 27 | DRAFT | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_workbook.py` | 109 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |

## Re-run after the fixes

Same scan, re-run at the end of the DOCS work. Nothing marked "fixed" is left. Every remaining hit is exempt, with its reason, or routed above.

| File | Lines | Term | Action |
|---|---|---|---|
| `.github/workflows/ci.yml` | 6 | job | exempt: YAML key `jobs:` |
| `.gitignore` | 40 | agent notes | exempt: ignore rules that keep the private paths out of git |
| `.gitignore` | 41 | LinkedIn | exempt: ignore rules that keep the private paths out of git |
| `archive/v1/README.md` | 12 | legacy | routed: lead |
| `archive/v1/README.md` | 18 | 787 | routed: lead |
| `archive/v1/README.md` | 18 | A320 | routed: lead |
| `config/assumptions.yaml` | 41, 354 | A320 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | 49, 354 | 787 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | 221, 319, 321 | legacy | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | 229 | agent notes | exempt: frozen config (cannot be edited) |
| `config/optimiser.yaml` | 4 | agent notes | exempt: frozen config (cannot be edited) |
| `data/ground_truth/planted.json` | 6 | legacy | exempt: frozen artefact / frozen simulator code |
| `docs/DECISIONS.md` | 13, 32, 44, 88 | legacy | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 16 | placeholder | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 18, 117 | interview | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 73, 112 | 787 | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | 112 | A320 | routed: lead (DECISIONS.md is lead-written) |
| `docs/assets/readme/pipeline.svg` | 58 | legacy | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/aircraft-narrowbody.svg` | 3 | A320 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/aircraft-widebody.svg` | 3 | 787 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/src/aircraft-plan.mjs` | 2, 236 | A320 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/src/aircraft-plan.mjs` | 3, 265 | 787 | routed: lead (unowned assets; aria text and README image) |
| `docs/assumption_register.md` | 414, 426, 479 | legacy | routed: lead (generator scripts/render_data_dictionary.py, relabel table) |
| `docs/css/components.css` | 511 | placeholder | exempt: CSS comment or `::placeholder` selector |
| `docs/css/motion.css` | 15 | legacy | exempt: CSS comment or `::placeholder` selector |
| `docs/css/views/data-method.css` | 29 | placeholder | exempt: CSS comment or `::placeholder` selector |
| `docs/design-review/REVIEW_LOG.md` | 11, 67 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | 179 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | 207 | LinkedIn | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | 207 | add link | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design/DESIGN_SYSTEM.md` | 211 | legacy | routed: lead (design-system gallery sample copy) |
| `docs/design/gallery.js` | 86 | legacy | routed: lead (design-system gallery sample copy) |
| `docs/design/gallery.js` | 134 | placeholder | routed: lead (design-system gallery sample copy) |
| `docs/js/charts/theme.js` | 393 | legacy | exempt: code comment |
| `docs/js/ui.js` | 1235 | placeholder | exempt: code comment |
| `docs/js/views/data-method.js` | 338 | placeholder | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/glossary.js` | 53 | placeholder | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/network-positioning.js` | 119, 228 | legacy | exempt: code comment |
| `docs/js/views/parts-intelligence.js` | 222 | placeholder | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/rotable-repair.js` | 131, 132, 185, 190, 352, 456, 521 | job | routed: ROUTER (Simple-mode copy says 'repair job(s)') |
| `notebooks/01_simulation_audit.ipynb` | 1030, 1069 | legacy | exempt: recorded cell output printing a frozen artefact's variant key |
| `outputs/calibration/v2_p0_gap_diagnosis.json` | 5475 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | 67, 124, 153, 263, 309, 345 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | 139 | A320 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_variants.json` | 270 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/holdout/truth_recovery.json` | 44 | legacy | exempt: frozen artefact / frozen simulator code |
| `outputs/policies/tuning_v1/iter0_policies.json` | 7 | legacy | exempt: frozen artefact / frozen simulator code |
| `reports/RELEASE_GATES.md` | 24 | LinkedIn | routed: lead (stale claim: the drafts are no longer in presentations/) |
| `reports/audit/keyboard/rotables.json` | 255, 266 | job | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/audit/links_downloads.json` | 828, 831 | interview | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/audit/numbers_reconcile.json` | 157 | LinkedIn | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/cutaway_critique_r1.md` | 39 | A320 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r1.md` | 39 | Airbus | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r1.md` | 39 | Boeing | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r2.md` | 49 | Airbus | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r2.md` | 49 | Boeing | routed: lead (AI review records; move to the private repo or reword) |
| `reports/junit.xml` | 1 | placeholder | exempt: test name `test_no_placeholder_left` |
| `reports/review_aviation.md` | 5 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 9, 29, 57 | interview | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 17, 19, 31 | 787 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 17, 19, 31 | A320 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 18, 19, 23, 40 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | 29 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 5 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 16, 28, 37 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 30, 39, 46, 47, 77 | A320 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 34, 38, 39, 41, 46, 77 | 787 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 42 | job | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | 87 | interview | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | 20, 21, 26, 39, 84 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | 36 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | 91 | interview | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design.md` | 112, 253 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design.md` | 211 | job | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 33, 128, 153, 189 | LinkedIn | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 33, 128, 153 | add link | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 71, 201 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | 128, 153 | placeholder | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | 42 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | 42 | legacy | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | 244 | recruiter | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_5.md` | 190, 309 | hire/hiring | routed: lead (AI review records; move to the private repo or reword) |
| `scripts/build_deck.py` | 745, 756 | job | exempt: local variable `jobs` |
| `scripts/build_deck.py` | 1790 | legacy | exempt: stale-label gate list in code |
| `scripts/dev/make_fixtures.mjs` | 3, 29, 112, 119, 131, 135, 151, 164, 182, 191, 217, 221, 228, 234 | placeholder | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/dev/make_fixtures.mjs` | 114 | legacy | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/notebooks/nb01.py` | 9 | hire/hiring | routed: lead (notebook generator; the notebook itself is fixed) |
| `scripts/render_data_dictionary.py` | 23, 24 | 787 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_data_dictionary.py` | 23, 24 | A320 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_docs.py` | 3, 12, 51, 1409, 1412, 1416 | placeholder | exempt: code identifier (`PLACEHOLDER` regex) and docstring |
| `scripts/render_docs.py` | 723, 1014, 1015, 1016, 1017, 1018 | legacy | exempt: relabel table / code comment |
| `scripts/render_docs.py` | 1010, 1011, 1012, 1013 | 787 | exempt: relabel table / code comment |
| `scripts/render_docs.py` | 1010, 1011, 1012, 1013 | A320 | exempt: relabel table / code comment |
| `scripts/v2_p0_variants_measure.py` | 4, 60 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/01_top_aog_drivers.sql` | 4 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/05_lead_time_drift.sql` | 8 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/07_d0_outstation_no_stock.sql` | 3, 9 | legacy | exempt: code comment / docstring (not a product surface) |
| `sql/run_all.py` | 9 | legacy | exempt: code comment / docstring (not a product surface) |
| `src/gnm/eval/truth_recovery.py` | 4 | legacy | exempt: code comment / docstring (not a product surface) |
| `src/gnm/export/build_site_data.py` | 194 | legacy | exempt: code comment |
| `src/gnm/export/v21.py` | 138, 167, 168, 169, 170, 171, 179 | legacy | exempt: scrub/gate patterns that remove these words |
| `src/gnm/policy/evaluate_policies.py` | 7 | legacy | exempt: code comment / docstring (not a product surface) |
| `src/gnm/sim/engine.py` | 1372, 1373, 1376, 1380 | job | exempt: frozen artefact / frozen simulator code |
| `src/gnm/sim/generator.py` | 359 | legacy | exempt: frozen artefact / frozen simulator code |
| `tests/test_docs_rendered.py` | 1, 45 | placeholder | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 26 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 27 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 27 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 28 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | 28 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 319, 330 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 320 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | 330 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | 173 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 15 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | 16 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_data.py` | 256, 258, 262 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_data.py` | 257, 258 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | 32, 33, 34 | LinkedIn | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | 32 | placeholder | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | 33 | add link | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | 787 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | A320 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | Airbus | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | Boeing | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | Etihad | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | 182 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | 29 | LinkedIn | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | 29 | interview | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | 29 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_workbook.py` | 109 | legacy | exempt: test code (forbidden-word lists, test names, browser assertions) |

**Gate.** `tests/test_public_scan.py` passes. It applies the same terms to the product surfaces, with comments stripped and a 4-entry ALLOW list for code identifiers. Its `PENDING` list holds only the routed rotable-repair copy. It also asserts that none of these paths is tracked: `study/`, `STUDY_GUIDE.md`, `PROGRESS.md`, `docs/agent_notes/`, `presentations/linkedin_*`, `presentations/video_script.md`, `private/`.
