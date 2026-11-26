"""Freeze-hash integrity: tampering after freeze is detected; holdout runs once."""
import json

import pytest

from gnm import freeze as F


@pytest.fixture
def tmp_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "ROOT", tmp_path)
    monkeypatch.setattr(F, "FREEZE_DIR", tmp_path / "freeze")
    monkeypatch.setattr(F, "MANIFEST", tmp_path / "freeze" / "manifest.json")
    monkeypatch.setattr(F, "HOLDOUT_LOG", tmp_path / "freeze" / "holdout_log.json")
    return tmp_path


def test_freeze_verify_and_tamper(tmp_freeze):
    a = tmp_freeze / "champions.csv"
    a.write_text("pn,method\nX,croston\n")
    F.freeze([a])
    F.verify()
    a.write_text("pn,method\nX,tsb\n")
    with pytest.raises(RuntimeError, match="changed"):
        F.verify()


def test_holdout_runs_once(tmp_freeze):
    a = tmp_freeze / "p.csv"
    a.write_text("x")
    F.freeze([a])
    F.require_frozen("policy_holdout")
    with pytest.raises(RuntimeError, match="already executed"):
        F.require_frozen("policy_holdout")
    log = json.loads((tmp_freeze / "freeze" / "holdout_log.json").read_text())
    assert len(log) == 1


def test_unfrozen_refuses(tmp_freeze):
    with pytest.raises(RuntimeError, match="Not frozen"):
        F.require_frozen("x")
