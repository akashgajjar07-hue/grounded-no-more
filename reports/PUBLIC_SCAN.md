# Public scan (v2.2)

A full scan of the public repo for wording that does not belong on a public project page: before the v2.2 fixes, and after them. This report names **categories only**. It does not repeat the words it looks for, and it quotes no hit context.

## Method

- **Files.** Every file in `git ls-files` that holds text: Markdown, code, JSON, CSV, YAML, templates, SQL, notebooks, XML and SVG. The text inside the deck (PPTX and both PDFs) and the planner workbook is included.
- **Categories:**
  - **personal terms**: words about job applications and personal preparation;
  - **internal-process terms**: words about how the project was produced (tooling instructions, working notes);
  - **placeholder / unfinished markers**: to-do markers, "fill in later" text, draft labels, filler text;
  - **OEM / airline names**: real manufacturer, airline and aircraft-type names (numbers such as coordinates do not count);
  - **outdated policy wording**: the old name for the starting-point policy, now the Simple Rulebook (naive reference).
- **Counting.** One hit is one line matching one category term. Counts are per file and category.
- **What counts.** Only user-visible text and docs. Exempt, with the reason given in the tables:
  - code identifiers, code comments and test code;
  - HTML input attributes;
  - the frozen config, outputs and simulator code (they cannot be edited);
  - this report and the link-check report.
- **The gate.** `tests/test_public_scan.py` applies the same categories to the product surfaces on every run:
  - site, rendered docs, deck text and workbook text;
  - comments are stripped first, and a 4-entry allow-list covers HTML input attributes;
  - the personal and internal-process word lists are stored base64-encoded so that they are not shown in the file;
  - the test also asserts that the files moved out of the public repo stay untracked.

## Totals

| | Hits | Fixed | Exempt | Routed | Regenerated |
|---|---|---|---|---|---|
| First scan (before v2.2) | 298 | 63 (DOCS) | 134 | 100 | 1 |
| Re-run (end of the DOCS pass) | 207 | none left | 165 | 42 (open, lead) | — |

Most routed hits were fixed during the run by their owners: ROUTER, PAGES and the lead. The 42 still open are all in review records and the decision log, which the lead owns.

**What DOCS fixed:**
- Outdated policy wording, everywhere it appeared in:
  - the doc templates and rendered docs;
  - the render script;
  - the site export text fields;
  - the deck and the workbook.
- A relabel pass in the export (`v21.scrub`) and in `render_docs.relabel` catches the frozen config's wording before it reaches any surface.
- Career / personal-prep and internal-process material:
  - the social-media generator moved out of the public deck script;
  - one notebook sentence was reworded;
  - the README and MODEL_CARD were stripped of employer, city and career framing.
- Placeholder / unfinished markers in the docs and the test-run file (`reports/junit.xml` regenerated).

## Open items (lead)

- `reports/review_*.md` and `reports/cutaway_critique_r1.md` / `_r2.md` (AI review records): move them to the private repo or reword them. LIMITATIONS and VALIDATION_REPORT link these records, so tell DOCS first and the links will be removed.
- `reports/CEO_REVIEW.md` (review record) quotes the findings it reports. Same choice: move it or reword it.
- `docs/DECISIONS.md`: one line of outdated policy wording remains.

## First scan, by file and category

| File | Category | Hits | Action |
|---|---|---|---|
| `.github/workflows/ci.yml` | personal | 1 | exempt: YAML key `jobs:` |
| `.gitignore` | internal-process | 1 | exempt: ignore rules that keep the private paths out of git |
| `.gitignore` | personal | 1 | exempt: ignore rules that keep the private paths out of git |
| `LIMITATIONS.md` | outdated policy wording | 3 | fixed (DOCS) |
| `METHODOLOGY.md` | outdated policy wording | 5 | fixed (DOCS) |
| `README.md` | outdated policy wording | 1 | fixed (DOCS) |
| `archive/v1/README.md` | outdated policy wording | 1 | routed: lead |
| `archive/v1/README.md` | OEM / airline names | 2 | routed: lead |
| `config/assumptions.yaml` | OEM / airline names | 4 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | outdated policy wording | 3 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | internal-process | 1 | exempt: frozen config (cannot be edited) |
| `config/optimiser.yaml` | internal-process | 1 | exempt: frozen config (cannot be edited) |
| `data/ground_truth/planted.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `docs/DECISIONS.md` | outdated policy wording | 4 | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | placeholder / unfinished | 1 | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | personal | 2 | routed: lead (DECISIONS.md is lead-written) |
| `docs/DECISIONS.md` | OEM / airline names | 1 | routed: lead (DECISIONS.md is lead-written) |
| `docs/assets/readme/pipeline.svg` | outdated policy wording | 1 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/aircraft-narrowbody.svg` | OEM / airline names | 1 | routed: lead (unowned assets; aria text and README image) |
| `docs/assets/svg/src/aircraft-plan.mjs` | OEM / airline names | 4 | routed: lead (unowned assets; aria text and README image) |
| `docs/assumption_register.md` | outdated policy wording | 3 | routed: lead (generator scripts/render_data_dictionary.py, relabel table) |
| `docs/css/components.css` | placeholder / unfinished | 1 | exempt: CSS comment or `::placeholder` selector |
| `docs/css/motion.css` | outdated policy wording | 1 | exempt: CSS comment or `::placeholder` selector |
| `docs/css/views/data-method.css` | placeholder / unfinished | 1 | exempt: CSS comment or `::placeholder` selector |
| `docs/data/kpis.json` | outdated policy wording | 1 | fixed (DOCS) |
| `docs/data/method.json` | outdated policy wording | 1 | fixed (DOCS) |
| `docs/design-review/REVIEW_LOG.md` | placeholder / unfinished | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | outdated policy wording | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design-review/REVIEW_LOG.md` | personal | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `docs/design/DESIGN_SYSTEM.md` | outdated policy wording | 1 | routed: lead (design-system gallery sample copy) |
| `docs/design/gallery.js` | outdated policy wording | 1 | routed: lead (design-system gallery sample copy) |
| `docs/design/gallery.js` | placeholder / unfinished | 1 | routed: lead (design-system gallery sample copy) |
| `docs/js/charts/theme.js` | outdated policy wording | 1 | exempt: code comment |
| `docs/js/ui.js` | placeholder / unfinished | 1 | exempt: code comment |
| `docs/js/views/capital-optimiser.js` | outdated policy wording | 1 | fixed by ROUTER during this run |
| `docs/js/views/data-method.js` | personal | 3 | fixed by PAGES during this run (chip and comment removed) |
| `docs/js/views/data-method.js` | placeholder / unfinished | 1 | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/data-method.js` | placeholder / unfinished | 1 | fixed by PAGES during this run (chip and comment removed) |
| `docs/js/views/glossary.js` | placeholder / unfinished | 1 | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/network-positioning.js` | outdated policy wording | 2 | exempt: code comment |
| `docs/js/views/network-positioning.js` | outdated policy wording | 2 | fixed by ROUTER during this run |
| `docs/js/views/parts-intelligence.js` | placeholder / unfinished | 1 | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/planner.js` | placeholder / unfinished | 3 | fixed by PAGES during this run (badge removed) |
| `docs/js/views/rotable-repair.js` | personal | 7 | routed: ROUTER (Simple-mode labels use a personal word) |
| `docs/templates/LIMITATIONS.md.tmpl` | outdated policy wording | 3 | fixed (DOCS) |
| `docs/templates/METHODOLOGY.md.tmpl` | outdated policy wording | 4 | fixed (DOCS) |
| `docs/templates/README.md.tmpl` | outdated policy wording | 1 | fixed (DOCS) |
| `docs/templates/VALIDATION_REPORT.md.tmpl` | placeholder / unfinished | 1 | fixed (DOCS) |
| `docs/templates/VALIDATION_REPORT.md.tmpl` | outdated policy wording | 1 | fixed (DOCS) |
| `notebooks/01_simulation_audit.ipynb` | personal | 1 | fixed (DOCS): career-framing sentence reworded |
| `notebooks/01_simulation_audit.ipynb` | outdated policy wording | 2 | exempt: recorded cell output printing a frozen artefact's variant key |
| `outputs/calibration/v2_p0_gap_diagnosis.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | outdated policy wording | 6 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | OEM / airline names | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_variants.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/holdout/truth_recovery.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/policies/tuning_v1/iter0_policies.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `reports/RELEASE_GATES.md` | personal | 1 | routed: lead (stale claim: the drafts are no longer in presentations/) |
| `reports/VALIDATION_REPORT.md` | placeholder / unfinished | 1 | fixed (DOCS) |
| `reports/VALIDATION_REPORT.md` | outdated policy wording | 7 | fixed (DOCS) |
| `reports/audit/keyboard/rotables.json` | personal | 2 | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/audit/links_downloads.json` | personal | 2 | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/audit/numbers_reconcile.json` | personal | 1 | routed: ROUTER (regenerate the audit file or mark it superseded) |
| `reports/cutaway_critique_r1.md` | OEM / airline names | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r2.md` | OEM / airline names | 2 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/junit.xml` | placeholder / unfinished | 1 | regenerated (old run with 1 failure replaced) |
| `reports/review_aviation.md` | personal | 4 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | OEM / airline names | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | outdated policy wording | 4 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | placeholder / unfinished | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | personal | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | outdated policy wording | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | OEM / airline names | 9 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | placeholder / unfinished | 5 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | outdated policy wording | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | personal | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design.md` | personal | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | personal | 4 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | placeholder / unfinished | 5 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | outdated policy wording | 2 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | personal | 2 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_3.md` | outdated policy wording | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_5.md` | personal | 2 | routed: lead (AI review records; move to the private repo or reword) |
| `scripts/build_deck.py` | placeholder / unfinished | 9 | fixed (DOCS): carousel and post generator moved to private/scripts/build_social.py (git-ignored) |
| `scripts/build_deck.py` | personal | 8 | fixed (DOCS): carousel and post generator moved to private/scripts/build_social.py (git-ignored) |
| `scripts/build_deck.py` | personal | 2 | exempt: local variable `jobs` |
| `scripts/build_deck.py` | outdated policy wording | 1 | exempt: stale-label gate list in code |
| `scripts/dev/make_fixtures.mjs` | placeholder / unfinished | 14 | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/dev/make_fixtures.mjs` | outdated policy wording | 1 | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/notebooks/nb01.py` | personal | 1 | routed: lead (notebook generator; the notebook itself is fixed) |
| `scripts/render_data_dictionary.py` | OEM / airline names | 4 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_docs.py` | placeholder / unfinished | 6 | exempt: code identifier (`PLACEHOLDER` regex) and docstring |
| `scripts/render_docs.py` | outdated policy wording | 4 | fixed (DOCS) |
| `scripts/render_docs.py` | outdated policy wording | 1 | exempt: relabel table / code comment |
| `scripts/render_docs.py` | OEM / airline names | 8 | exempt: relabel table / code comment |
| `scripts/v2_p0_variants_measure.py` | outdated policy wording | 2 | exempt: code comment / docstring (not a product surface) |
| `sql/01_top_aog_drivers.sql` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `sql/05_lead_time_drift.sql` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `sql/07_d0_outstation_no_stock.sql` | outdated policy wording | 2 | exempt: code comment / docstring (not a product surface) |
| `sql/run_all.py` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `src/gnm/eval/truth_recovery.py` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `src/gnm/export/build_site_data.py` | outdated policy wording | 1 | exempt: code comment |
| `src/gnm/export/build_site_data.py` | outdated policy wording | 2 | fixed (DOCS) |
| `src/gnm/export/v21.py` | outdated policy wording | 1 | exempt: scrub/gate patterns that remove these words |
| `src/gnm/policy/evaluate_policies.py` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `src/gnm/sim/engine.py` | personal | 4 | exempt: frozen artefact / frozen simulator code |
| `src/gnm/sim/generator.py` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `tests/test_docs_rendered.py` | placeholder / unfinished | 2 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | OEM / airline names | 4 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | OEM / airline names | 9 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_data.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | personal | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | placeholder / unfinished | 2 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | placeholder / unfinished | 2 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_workbook.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |

## Re-run at the end of the DOCS pass

Nothing marked "fixed" is left. Every remaining hit is exempt, with its reason, or open with the lead as listed above.

| File | Category | Hits | Action |
|---|---|---|---|
| `.github/workflows/ci.yml` | personal | 1 | exempt: YAML key `jobs:` |
| `.gitignore` | internal-process | 1 | exempt: ignore rules that keep the private paths out of git |
| `.gitignore` | personal | 1 | exempt: ignore rules that keep the private paths out of git |
| `config/assumptions.yaml` | OEM / airline names | 4 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | outdated policy wording | 3 | exempt: frozen config (cannot be edited) |
| `config/assumptions.yaml` | internal-process | 1 | exempt: frozen config (cannot be edited) |
| `config/optimiser.yaml` | internal-process | 1 | exempt: frozen config (cannot be edited) |
| `data/ground_truth/planted.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `docs/DECISIONS.md` | outdated policy wording | 1 | routed: lead (DECISIONS.md is lead-written) |
| `docs/css/components.css` | placeholder / unfinished | 1 | exempt: CSS comment or `::placeholder` selector |
| `docs/css/motion.css` | outdated policy wording | 1 | exempt: CSS comment or `::placeholder` selector |
| `docs/css/views/data-method.css` | placeholder / unfinished | 1 | exempt: CSS comment or `::placeholder` selector |
| `docs/js/charts/theme.js` | outdated policy wording | 1 | exempt: code comment |
| `docs/js/ui.js` | placeholder / unfinished | 1 | exempt: code comment |
| `docs/js/views/data-method.js` | placeholder / unfinished | 1 | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/glossary.js` | placeholder / unfinished | 1 | exempt: HTML `placeholder` attribute (ALLOW list) |
| `docs/js/views/network-positioning.js` | outdated policy wording | 2 | exempt: code comment |
| `docs/js/views/parts-intelligence.js` | placeholder / unfinished | 1 | exempt: HTML `placeholder` attribute (ALLOW list) |
| `notebooks/01_simulation_audit.ipynb` | outdated policy wording | 2 | exempt: recorded cell output printing a frozen artefact's variant key |
| `outputs/calibration/v2_p0_gap_diagnosis.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | outdated policy wording | 6 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_gap_diagnosis.md` | OEM / airline names | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/calibration/v2_p0_variants.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/holdout/truth_recovery.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `outputs/policies/tuning_v1/iter0_policies.json` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `reports/cutaway_critique_r1.md` | OEM / airline names | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/cutaway_critique_r2.md` | OEM / airline names | 2 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/junit.xml` | placeholder / unfinished | 1 | exempt: a test name |
| `reports/review_aviation.md` | OEM / airline names | 6 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | outdated policy wording | 4 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation.md` | placeholder / unfinished | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | outdated policy wording | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_aviation_v2.md` | OEM / airline names | 11 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | placeholder / unfinished | 5 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_correctness.md` | outdated policy wording | 1 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | placeholder / unfinished | 3 | routed: lead (AI review records; move to the private repo or reword) |
| `reports/review_design_2.md` | outdated policy wording | 2 | routed: lead (AI review records; move to the private repo or reword) |
| `scripts/build_deck.py` | personal | 2 | exempt: local variable `jobs` |
| `scripts/build_deck.py` | outdated policy wording | 1 | exempt: stale-label gate list in code |
| `scripts/dev/make_fixtures.mjs` | placeholder / unfinished | 14 | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/dev/make_fixtures.mjs` | outdated policy wording | 1 | exempt: dev-only layout fixtures (never exported or deployed) |
| `scripts/render_data_dictionary.py` | outdated policy wording | 2 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_data_dictionary.py` | OEM / airline names | 4 | exempt: relabel table (code identifiers that remove these names) |
| `scripts/render_docs.py` | placeholder / unfinished | 6 | exempt: code identifier (`PLACEHOLDER` regex) and docstring |
| `scripts/render_docs.py` | outdated policy wording | 6 | exempt: relabel table / code comment |
| `scripts/render_docs.py` | OEM / airline names | 8 | exempt: relabel table / code comment |
| `scripts/v2_p0_variants_measure.py` | outdated policy wording | 2 | exempt: code comment / docstring (not a product surface) |
| `sql/01_top_aog_drivers.sql` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `sql/05_lead_time_drift.sql` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `sql/07_d0_outstation_no_stock.sql` | outdated policy wording | 2 | exempt: code comment / docstring (not a product surface) |
| `sql/run_all.py` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `src/gnm/eval/truth_recovery.py` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `src/gnm/export/build_site_data.py` | outdated policy wording | 1 | exempt: code comment |
| `src/gnm/export/v21.py` | outdated policy wording | 7 | exempt: scrub/gate patterns that remove these words |
| `src/gnm/policy/evaluate_policies.py` | outdated policy wording | 1 | exempt: code comment / docstring (not a product surface) |
| `src/gnm/sim/engine.py` | personal | 4 | exempt: frozen artefact / frozen simulator code |
| `src/gnm/sim/generator.py` | outdated policy wording | 1 | exempt: frozen artefact / frozen simulator code |
| `tests/test_docs_rendered.py` | placeholder / unfinished | 2 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_docs_rendered.py` | OEM / airline names | 4 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_public_scan.py` | placeholder / unfinished | 12 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_public_scan.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | OEM / airline names | 9 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_reconciliation.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_about.py` | placeholder / unfinished | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_aog.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_cutaway.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_data.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | personal | 3 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_method.py` | placeholder / unfinished | 2 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | OEM / airline names | 5 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_optimiser.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | personal | 2 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_site_planner.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
| `tests/test_workbook.py` | outdated policy wording | 1 | exempt: test code (forbidden-word lists, test names, browser assertions) |
