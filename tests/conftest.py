"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
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
    return tmp_path.resolve()


@pytest.fixture
def mock_target() -> Iterator[None]:
    """Start the three-port mock HTTP target used by httpx_probe e2e tests.

    Lives here (root conftest) rather than in tests/fixtures/mock_target/
    because pytest does not collect conftest files from inside __init__.py
    package subdirectories when those directories are off the testpaths.
    """
    from tests.fixtures.mock_target.server import (
        start_mock_target,
        stop_mock_target,
    )

    servers = start_mock_target()
    try:
        yield
    finally:
        stop_mock_target(servers)
