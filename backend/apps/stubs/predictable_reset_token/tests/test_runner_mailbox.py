"""Tests for stub 2.5 runner mailbox-loading error path.

Covers _load_mailbox_or_refuse when load_mailbox_backend raises
MailboxConfigError → emits AUTH_PROBE_REFUSED with reason=missing_secret.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import get_registry
from apps.stubs._test_factories import seed_target_run
from apps.stubs._shared.auth.mailbox import MailboxConfigError
from apps.stubs.predictable_reset_token.runner import run
from apps.stubs.predictable_reset_token.tests._helpers import _program


@pytest.mark.django_db
def test_mailbox_config_error_emits_missing_secret() -> None:
    """When load_mailbox_backend raises MailboxConfigError (e.g. missing
    env vars), the runner records MISSING_SECRET and returns."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program()), \
         patch(
             "apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
             side_effect=MailboxConfigError("FIXTURE_MAILBOX_BACKEND not set"),
         ):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["missing_secret"] == "FIXTURE_MAILBOX_*"
    assert "FIXTURE_MAILBOX_BACKEND not set" in ev.data["error"]
