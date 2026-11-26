"""e2e conftest (QA): registers the `audit` marker and keeps audit tests out of the default run.

`audit` tests (full interaction matrix, external-link checks) are slow or need the network. They run only when
selected explicitly: `pytest -m audit tests/e2e` (or GNM_AUDIT=1).
"""
from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "audit: release-grade interaction / network audit (excluded unless -m audit or GNM_AUDIT=1)")


def pytest_collection_modifyitems(config, items):
    expr = config.getoption("-m") or ""
    if "audit" in expr and "not audit" not in expr or os.environ.get("GNM_AUDIT") == "1":
        return
    skip = pytest.mark.skip(reason="audit test: run with `pytest -m audit` (or GNM_AUDIT=1)")
    for it in items:
        if "audit" in it.keywords:
            it.add_marker(skip)
