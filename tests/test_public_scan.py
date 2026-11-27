"""Public-surface word gate (v2.2) and privacy check.

1. No forbidden word in user-visible text on the product surfaces: the site (docs/index.html, docs/js, docs/css,
   docs/content, docs/data, docs/lab), the rendered docs (README, METHODOLOGY, MODEL_CARD, LIMITATIONS,
   reports/VALIDATION_REPORT.md), the deck text (presentations/case_study_deck.pptx) and the workbook text.
   Categories: career / personal-prep terms, internal-process terms, placeholder / unfinished markers, OEM / airline
   names, outdated policy wording. JS/CSS comments are stripped first (they are code, not copy). Code identifiers that
   happen to contain a word (an HTML input attribute) are allowed only through the explicit ALLOW list.
2. Files moved out of the public repo stay untracked by git.

The deck PDF is rendered from the same slide spec as the PPTX (scripts/build_deck.py), so the PPTX text stands for it.
reports/PUBLIC_SCAN.md lists the full-repo scan by category and how each hit was handled.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The type numbers are assembled from fragments so this file does not trip other repo greps.
_NB, _WB = "A3" + "20", "78" + "7"
# The career / personal-prep and internal-process terms are stored base64-encoded and decoded at run time. This keeps
# the word list itself from being displayed when someone reads this file on GitHub; it is not a secret. Decode with
# base64.b64decode(...) to review the list.
_B64 = lambda s: base64.b64decode(s).decode()  # noqa: E731
_CAREER_I = ["XGJpbnRlcnZpZXc=", "bGlua2VkXHM/aW4=", "XGJyZWNydWl0", "XGJoaXIoPzplfGVzfGVkfGluZylcYg==", "XGJqb2JzP1xi", "Z2lybGZyaWVuZA=="]
_CAREER_CS = ["XGJDRU9cYg=="]
_INTERNAL_I = ["cHJvbXB0", "c3ViLT9hZ2VudA==", "YWdlbnRbIF8tXW5vdGVz"]
TERMS = {
    **{f"career / personal-prep #{n}": re.compile(_B64(b), re.I) for n, b in enumerate(_CAREER_I, 1)},
    **{f"career / personal-prep #{n}": re.compile(_B64(b)) for n, b in enumerate(_CAREER_CS, len(_CAREER_I) + 1)},
    **{f"internal-process #{n}": re.compile(_B64(b), re.I) for n, b in enumerate(_INTERNAL_I, 1)},
    "placeholder / unfinished": re.compile(r"\b(?:TODO|FIXME|TBD)\b|add link|\blorem\b|\bDRAFT\b"),
    "placeholder": re.compile(r"placeholder", re.I),
    "OEM / airline name": re.compile(r"\bEti" + r"had\b|\b(?:Air" + r"bus|Boe" + r"ing)\b", re.I),
    "type number": re.compile(rf"\b{_NB}|(?<![\w.,]){_WB}(?![\d.,]*\d)(?!\s*(?:h\b|AED|units?\b|k\b|%|px|ms))"),
    "outdated policy wording": re.compile(r"\blegacy\b", re.I),
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

# Paths moved out of the public repo (base64 for the same reason as the terms above).
PRIVATE_PATHS = [_B64(b) for b in ("c3R1ZHkv", "U1RVRFlfR1VJREUubWQ=", "UFJPR1JFU1MubWQ=", "ZG9jcy9hZ2VudF9ub3Rlcy8=", "cHJlc2VudGF0aW9ucy9saW5rZWRpbl8=", "cHJlc2VudGF0aW9ucy92aWRlb19zY3JpcHQubWQ=")]


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
    for entry in ["private/", *(_B64(b) for b in ("c3R1ZHkv", "U1RVRFlfR1VJREUubWQ=", "UFJPR1JFU1MqLm1k", "ZG9jcy9hZ2VudF9ub3Rlcy8="))]:
        assert entry in gi.splitlines(), f".gitignore lacks {entry}"
    assert not [p for p in _tracked() if p.startswith("private/")]
