"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clean throwaway repo root for tests that touch the filesystem."""
    (tmp_path / "programs").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path
