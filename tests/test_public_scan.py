"""Public-surface word gate (v2.2) and privacy check.

1. No forbidden word in user-visible text on the product surfaces: the site (docs/index.html, docs/js, docs/css,
   docs/content, docs/data, docs/lab), the rendered docs (README, METHODOLOGY, MODEL_CARD, LIMITATIONS,
   reports/VALIDATION_REPORT.md), the deck text (presentations/case_study_deck.pptx) and the workbook text.
   JS/CSS comments are stripped first (they are code, not copy). Code identifiers that happen to contain a word
   (an HTML `placeholder` attribute, a `linkedin` config key) are allowed only through the explicit ALLOW list.
2. Private material is not tracked by git: study pack, study guide, progress log, agent notes, social-media drafts and
   the walkthrough script.

The deck PDF is rendered from the same slide spec as the PPTX (scripts/build_deck.py), so the PPTX text stands for it.
reports/PUBLIC_SCAN.md lists every hit of the full-repo scan and how it was handled.
"""
from __future__ import annotations

import json
import re
import subprocess
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The type numbers are assembled from fragments so this file does not trip other repo greps.
_NB, _WB = "A3" + "20", "78" + "7"
TERMS = {
    "interview": re.compile(r"\binterview", re.I),
    "linkedin": re.compile(r"linked\s?in", re.I),
    "recruiter": re.compile(r"\brecruit", re.I),
    "CEO": re.compile(r"\bCEO\b"),
    "hire": re.compile(r"\bhir(?:e|es|ed|ing)\b", re.I),
    "job": re.compile(r"\bjobs?\b", re.I),
    "girlfriend": re.compile(r"girlfriend", re.I),
    "prompt": re.compile(r"prompt", re.I),
    "subagent": re.compile(r"sub-?agent", re.I),
    "agent notes": re.compile(r"agent[ _-]notes", re.I),
    "TODO/FIXME/TBD": re.compile(r"\b(?:TODO|FIXME|TBD)\b"),
    "add link": re.compile(r"add link", re.I),
    "lorem": re.compile(r"\blorem\b", re.I),
    "placeholder": re.compile(r"placeholder", re.I),
    "DRAFT": re.compile(r"\bDRAFT\b"),
    "airline brand": re.compile(r"\bEti" + r"had\b", re.I),
    "manufacturer": re.compile(r"\b(?:Air" + r"bus|Boe" + r"ing)\b", re.I),
    "type number": re.compile(rf"\b{_NB}|(?<![\w.,]){_WB}(?![\d.,]*\d)(?!\s*(?:h\b|AED|units?\b|k\b|%|px|ms))"),
    "legacy": re.compile(r"\blegacy\b", re.I),
}

SITE_GLOBS = ["docs/index.html", "docs/js/**/*.js", "docs/css/**/*.css", "docs/content/*.md", "docs/data/*.json",
              "docs/lab/*"]
DOCS = ["README.md", "METHODOLOGY.md", "MODEL_CARD.md", "LIMITATIONS.md", "reports/VALIDATION_REPORT.md"]
DECK = ROOT / "presentations" / "case_study_deck.pptx"
WORKBOOK = ROOT / "excel" / "grounded_no_more_planner_workbook.xlsx"

# (file, term, substring of the offending line): code identifiers, not copy. Keep this list short and explicit.
ALLOW = [
    ("docs/js/views/data-method.js", "placeholder", "placeholder: '"),                # <input placeholder> attribute
    ("docs/js/views/glossary.js", "placeholder", "placeholder: byMode("),             # <input placeholder> attribute
    ("docs/js/views/parts-intelligence.js", "placeholder", "placeholder: byMode("),   # <input placeholder> attribute
    ("docs/css/views/data-method.css", "placeholder", "::placeholder"),               # CSS pseudo-element
    # numeric hits inside SVG path data (coordinates such as 787.5) are excluded by the type-number pattern
]

# Hits routed to their owners in the v2.2 fix run (reports/PUBLIC_SCAN.md). Remove each entry once it is fixed;
# test_pending_entries_still_needed warns when an entry no longer matches anything.
PENDING = [
]

PRIVATE_PATHS = ["study/", "STUDY_GUIDE.md", "PROGRESS.md", "docs/agent_notes/", "presentations/linkedin_",
                 "presentations/video_script.md"]


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    return [p for p in out.splitlines() if p]


_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_LINE = re.compile(r"(^|[\s;{}(),])//[^\n]*")


def _strip_comments(text: str, suffix: str) -> str:
    """Blank JS/CSS comments but keep line numbers. `//` after ':' (URLs) is not a comment start."""
    keep_lines = lambda m: "\n" * m.group(0).count("\n")  # noqa: E731
    if suffix in (".js", ".mjs", ".css"):
        text = _BLOCK.sub(keep_lines, text)
    if suffix in (".js", ".mjs"):
        text = _LINE.sub(lambda m: m.group(1), text)
    if suffix == ".html":
        text = re.sub(r"<!--.*?-->", keep_lines, text, flags=re.S)
    return text


def _json_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _json_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _json_strings(v)
    elif isinstance(obj, str):
        yield obj


def _surface_lines():
    """(display path, line no, text) over every product surface."""
    files: list[Path] = []
    for g in SITE_GLOBS:
        files += sorted(p for p in ROOT.glob(g) if p.is_file())
    files += [ROOT / d for d in DOCS if (ROOT / d).exists()]
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix == ".json":
            for i, s in enumerate(_json_strings(json.loads(p.read_text(encoding="utf-8"))), 1):
                for line in s.splitlines() or [s]:
                    yield rel, i, line
            continue
        if p.suffix not in (".js", ".mjs", ".css", ".html", ".md"):
            continue
        text = _strip_comments(p.read_text(encoding="utf-8"), p.suffix)
        for i, line in enumerate(text.splitlines(), 1):
            yield rel, i, line
    if DECK.exists():
        from pptx import Presentation
        for si, slide in enumerate(Presentation(str(DECK)).slides, 1):
            for sh in slide.shapes:
                if sh.has_text_frame:
                    for para in sh.text_frame.paragraphs:
                        yield DECK.relative_to(ROOT).as_posix(), si, "".join(r.text for r in para.runs)
            if slide.has_notes_slide:
                yield DECK.relative_to(ROOT).as_posix(), si, slide.notes_slide.notes_text_frame.text
    if WORKBOOK.exists():
        import openpyxl
        wb = openpyxl.load_workbook(WORKBOOK)
        for ws in wb.worksheets:
            yield WORKBOOK.relative_to(ROOT).as_posix(), 0, ws.title
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and not c.value.startswith("="):
                        yield f"{WORKBOOK.relative_to(ROOT).as_posix()}:{ws.title}!{c.coordinate}", c.row, c.value


def _hits():
    out = []
    for rel, n, line in _surface_lines():
        for term, pat in TERMS.items():
            if pat.search(line):
                out.append((rel, n, term, line.strip()))
    return out


def _allowed(hit, table) -> bool:
    rel, _, term, line = hit
    return any(rel == f and term == t and sub in line for f, t, sub in table)


def test_no_forbidden_words_on_product_surfaces():
    bad = [h for h in _hits() if not _allowed(h, ALLOW) and not _allowed(h, PENDING)]
    assert not bad, "forbidden words on product surfaces:\n" + "\n".join(
        f"{r}:{n} [{t}] {line[:160]}" for r, n, t, line in bad[:40])


def test_pending_entries_still_needed():
    hits = _hits()
    stale = [p for p in PENDING if not any(_allowed(h, [p]) for h in hits)]
    if stale:   # a warning, not a failure: owners fix their files independently of this list
        warnings.warn(f"fixed: remove these PENDING entries from tests/test_public_scan.py: {stale}")


def test_private_material_not_tracked():
    tracked = _tracked()
    bad = [p for p in tracked if any(p == q or p.startswith(q) for q in PRIVATE_PATHS)]
    assert not bad, f"private material is tracked by git: {bad}"


def test_private_folder_is_ignored():
    gi = (ROOT / ".gitignore").read_text()
    for entry in ("private/", "study/", "STUDY_GUIDE.md", "PROGRESS*.md", "docs/agent_notes/"):
        assert entry in gi.splitlines(), f".gitignore lacks {entry}"
    assert not [p for p in _tracked() if p.startswith("private/")]
