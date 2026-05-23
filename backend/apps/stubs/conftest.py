"""Shared pytest fixtures for stub runner tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def _bypass_guard():
    """Patch resolve_and_guard so stub runners skip scope/rate-limit checks.

    Not autouse — stubs that set up a real program registry (OAuth family)
    must NOT apply this; they request it explicitly via pytestmark.
    """
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield
