"""Edge-case tests for stub 2.5 runner — uncovered branches.

Covers:
- allow_active_login_probes=True but allow_password_reset_probes=False
- discovery returns error
- scope enforcement fails (OutOfScope)
- request_reset returns False mid-collection
- mailbox returns None mid-collection
- extract_reset_token returns None
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import get_registry
from apps.stubs._shared.auth.mailbox import FakeMailbox, InboundMessage
from apps.stubs._test_factories import seed_target_run
from apps.stubs.predictable_reset_token.discovery import DiscoveryOutcome
from apps.stubs.predictable_reset_token.runner import run
from apps.stubs.predictable_reset_token.tests._helpers import (
    RESET_FORM, _DrainingMailbox, _program,
)


@pytest.mark.django_db
def test_only_active_login_knob_true_but_reset_probes_false_refused() -> None:
    """allow_active_login_probes=True but allow_password_reset_probes=False
    → the second refusal block fires, not the first."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    prog = _program(active_login=True, reset_probes=False)
    with patch.object(get_registry(), "find_for_host", return_value=prog):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "roe_disabled"
    assert ev.data["knob"] == "allow_password_reset_probes"


@pytest.mark.django_db
def test_discovery_transport_error_emits_probe_refused() -> None:
    """fetch_and_find_reset_form returns error → AUTH_PROBE_REFUSED
    with reason=transport_error."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=FakeMailbox(messages=[])), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=None, final_url="https://x.example/",
                   error="ConnectError",
               )):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "transport_error"
    assert ev.data["error"] == "ConnectError"


@pytest.mark.django_db
def test_scope_check_fails_on_final_url_skips_scan() -> None:
    """enforce_scope raises OutOfScope when the discovered reset form
    is on an out-of-scope host."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=FakeMailbox(messages=[])), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=RESET_FORM,
                   final_url="https://x.example/password-reset",
                   error=None,
               )), \
         patch("apps.stubs.predictable_reset_token.runner.enforce_scope",
               side_effect=OutOfScope("off-scope")):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_request_reset_false_breaks_collection_loop() -> None:
    """When request_reset returns False on the first attempt, the token
    collection loop breaks immediately and returns 0 tokens → STALE finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host",
                      return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=FakeMailbox(messages=[])), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=RESET_FORM,
                   final_url="https://x.example/password-reset",
                   error=None,
               )), \
         patch("apps.stubs.predictable_reset_token.runner.request_reset",
               return_value=False):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.status == FindingStatus.STALE
    assert f.data["sample_size"] == 0


@pytest.mark.django_db
def test_mailbox_returns_none_breaks_collection_loop() -> None:
    """When mailbox.wait_for_message returns None (timeout), the loop breaks."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")

    with patch.object(get_registry(), "find_for_host",
                      return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=_DrainingMailbox([])), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=RESET_FORM,
                   final_url="https://x.example/password-reset",
                   error=None,
               )), \
         patch("apps.stubs.predictable_reset_token.runner.request_reset",
               return_value=True):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.status == FindingStatus.STALE


@pytest.mark.django_db
def test_extract_reset_token_none_breaks_collection_loop() -> None:
    """When extract_reset_token returns None (no token param in URL),
    the loop breaks."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    now = datetime.now(timezone.utc)
    msg_no_token = InboundMessage(
        to_address="scanner@example.invalid",
        from_address="noreply@target.invalid",
        subject="Reset",
        body_text="https://x.example/reset?session_id=abc",
        body_html="",
        arrived_at=now,
        message_id="<x@target.invalid>",
    )

    with patch.object(get_registry(), "find_for_host",
                      return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=_DrainingMailbox([msg_no_token])), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=RESET_FORM,
                   final_url="https://x.example/password-reset",
                   error=None,
               )), \
         patch("apps.stubs.predictable_reset_token.runner.request_reset",
               return_value=True):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.status == FindingStatus.STALE
