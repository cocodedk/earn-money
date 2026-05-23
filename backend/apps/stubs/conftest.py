"""Shared pytest fixtures for stub runner tests."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def _bypass_guard():
    """Patch resolve_and_guard so stub runners skip scope/rate-limit checks.

    Not autouse — stubs that set up a real program registry (OAuth family,
    invitation-abuse, tenant-org-join) must NOT apply this fixture.
    Non-OAuth consumers opt in via pytestmark.
    """
    with patch("apps.stubs.runners.resolve_and_guard", return_value=MagicMock()):
        yield
