"""An empty home directory and no API key for every test."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "CLAUDECODE", "LINEAR_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path
