"""Freeze discipline: hash selection artefacts before any holdout run.

freeze(paths) writes outputs/freeze/manifest.json with SHA-256 of each artefact.
verify() recomputes hashes and raises if anything changed. Holdout runners must
call `require_frozen()` first; it also records the run in outputs/freeze/holdout_log.json
and refuses a second holdout run unless force=True (which is logged).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from gnm.config import OUTPUTS, ROOT

FREEZE_DIR = OUTPUTS / "freeze"
MANIFEST = FREEZE_DIR / "manifest.json"
HOLDOUT_LOG = FREEZE_DIR / "holdout_log.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze(paths: list[Path | str], note: str = "") -> dict:
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    entries = {}
    for p in paths:
        p = Path(p)
        if not p.is_absolute():
            p = ROOT / p
        entries[str(p.relative_to(ROOT))] = sha256_file(p)
    manifest = {"frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "note": note, "artefacts": entries}
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    return manifest


def verify() -> dict:
    if not MANIFEST.exists():
        raise RuntimeError("Not frozen: outputs/freeze/manifest.json missing")
    m = json.loads(MANIFEST.read_text())
    bad = {k: v for k, v in m["artefacts"].items() if sha256_file(ROOT / k) != v}
    if bad:
        raise RuntimeError(f"Frozen artefacts changed since freeze: {list(bad)}")
    return m


def require_frozen(run_name: str, force: bool = False) -> dict:
    m = verify()
    log = json.loads(HOLDOUT_LOG.read_text()) if HOLDOUT_LOG.exists() else []
    if any(r["run"] == run_name for r in log) and not force:
        raise RuntimeError(f"Holdout run '{run_name}' already executed; holdout runs once.")
    log.append({"run": run_name, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "manifest_frozen_at": m["frozen_at"], "forced": force})
    HOLDOUT_LOG.write_text(json.dumps(log, indent=2))
    return m
