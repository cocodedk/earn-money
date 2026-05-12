from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.fixtures.mock_target.server import start_mock_target, stop_mock_target


@pytest.fixture
def mock_target() -> Iterator[None]:
    servers = start_mock_target()
    try:
        yield
    finally:
        stop_mock_target(servers)
