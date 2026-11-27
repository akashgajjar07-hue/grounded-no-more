"""Rebuild docs/data/story.json alone from the exported site data (docs/data/*.json) with the story section of
gnm.export.build_site_data. The other exports are read, never written. Run: .venv/bin/python scripts/tour/regen_story.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gnm.export import build_site_data as B  # noqa: E402
from gnm.export import v21  # noqa: E402

SITE = ROOT / "docs" / "data"


def main() -> None:
    data = {n: json.loads((SITE / f"{n}.json").read_text()) for n in B.FILES if n != "story"}
    story = v21.scrub(B.clean(B.build_story(data)))
    bad = list(v21.text_violations(story))
    if bad:
        raise SystemExit(f"text gate: {bad[:3]}")
    (SITE / "story.json").write_text(B.dumps(story) + "\n")
    for s in story["steps"]:
        print(len(s["body"]), len(s["body_simple"]), s["title"], "|", s["body"])
        print("   simple:", s["body_simple"])


if __name__ == "__main__":
    main()
