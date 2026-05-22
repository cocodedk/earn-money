"""End-to-end tests for stub 2.5 detection chain.

Mock layers:
* `find_for_host` → returns a program with `allow_password_reset_probes=True`.
* `fetch_and_find_reset_form` → returns a synthesised AuthForm.
* `request_reset` → returns True (don't fire real HTTP).
* `load_mailbox_backend` → returns a mailbox pre-seeded with
  reset emails whose tokens match the scenario under test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import get_registry
from apps.stubs._shared.auth.mailbox import InboundMessage
from apps.stubs._test_factories import seed_target_run
from apps.stubs.predictable_reset_token.discovery import DiscoveryOutcome
from apps.stubs.predictable_reset_token.runner import run
from apps.stubs.predictable_reset_token.tests._helpers import (
    RESET_FORM, _DrainingMailbox, _program,
)


def _emails_with_tokens(tokens: list[str]) -> list[InboundMessage]:
    now = datetime.now(timezone.utc)
    return [
        InboundMessage(
            to_address="scanner@example.invalid",
            from_address="noreply@target.invalid",
            subject="Reset your password",
            body_text=f"Click: https://x.example/reset?token={t}",
            body_html="",
            arrived_at=now + timedelta(milliseconds=i),
            message_id=f"<{i}@target.invalid>",
        )
        for i, t in enumerate(tokens)
    ]


@pytest.mark.django_db
def test_sequential_integer_tokens_emit_critical_finding(monkeypatch) -> None:
    """Eight sequential-integer reset tokens → CRITICAL finding."""
    monkeypatch.setenv("FIXTURE_MAILBOX_BACKEND", "none")
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    tokens = [str(n) for n in range(1001, 1009)]
    msgs = _emails_with_tokens(tokens)

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(form=RESET_FORM,
                                             final_url="https://x.example/password-reset",
                                             error=None)), \
         patch("apps.stubs.predictable_reset_token.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=_DrainingMailbox(msgs)):
        run(scan_run, target_run)

    finding = Finding.objects.get(scan_run=scan_run)
    assert finding.category == "auth_predictable_reset_token"
    assert finding.severity == Severity.CRITICAL
    assert finding.confidence == "high"
    assert finding.data["signal"] == "sequential_integer"
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_random_uuid_tokens_emit_no_finding(monkeypatch) -> None:
    """Eight random UUIDs → no Finding."""
    import uuid
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    tokens = [str(uuid.uuid4()) for _ in range(8)]
    msgs = _emails_with_tokens(tokens)

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(form=RESET_FORM,
                                             final_url="https://x.example/password-reset",
                                             error=None)), \
         patch("apps.stubs.predictable_reset_token.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=_DrainingMailbox(msgs)):
        run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_mailbox_backend_none_emits_fixture_required() -> None:
    """`load_mailbox_backend()` returns None (BACKEND=none) → stub
    can't test reset → AUTH_FIXTURE_REQUIRED detail=mailbox_required_for_reset."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=None):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["detail"] == "mailbox_required_for_reset"


@pytest.mark.django_db
def test_no_reset_form_found_emits_fixture_required() -> None:
    """discover_forms returns nothing matching password_reset →
    AUTH_FIXTURE_REQUIRED detail=no_reset_form_found."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=_DrainingMailbox([])), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(
                   form=None, final_url="https://x.example/", error=None)):
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED,
    )
    assert ev.data["detail"] == "no_reset_form_found"


@pytest.mark.django_db
def test_too_few_tokens_emits_stale_finding() -> None:
    """Mailbox times out after first probe → 0 tokens collected →
    Finding(status=STALE, sample_size=0)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.5")

    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.predictable_reset_token.runner.fetch_and_find_reset_form",
               return_value=DiscoveryOutcome(form=RESET_FORM,
                                             final_url="https://x.example/password-reset",
                                             error=None)), \
         patch("apps.stubs.predictable_reset_token.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.predictable_reset_token.runner.load_mailbox_backend",
               return_value=_DrainingMailbox([])):
        run(scan_run, target_run)

    finding = Finding.objects.get(scan_run=scan_run)
    assert finding.status == FindingStatus.STALE
    assert finding.data["sample_size"] == 0
