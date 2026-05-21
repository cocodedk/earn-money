"""End-to-end detection tests for stub 2.6 (reset-token-reuse)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs._shared.auth.mailbox import FakeMailbox, InboundMessage
from apps.stubs._test_factories import seed_target_run
from apps.stubs.predictable_reset_token.discovery import DiscoveryOutcome
from apps.stubs.reset_token_reuse.runner import run


def _program() -> Program:
    return Program(
        platform="local", slug="reset-canary",
        scope=Scope(
            platform="local", slug="reset-canary",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_password_reset_probes=True,
            authorized_test_accounts=["scanner@example.invalid"],
        ),
    )


_RESET_FORM = AuthForm(
    method="POST",
    action_url="https://x.example/forgot-password",
    content_type="application/x-www-form-urlencoded",
    identifier_field="email", password_field=None,
    hidden_fields={}, flow_hint="password_reset",
)


def _outcome() -> DiscoveryOutcome:
    return DiscoveryOutcome(
        form=_RESET_FORM, final_url=_RESET_FORM.action_url, error=None,
    )


def _email_with_token(token: str) -> FakeMailbox:
    return FakeMailbox(messages=[InboundMessage(
        to_address="scanner@example.invalid",
        from_address="noreply@target.invalid",
        subject="Reset",
        body_text=f"Click https://x.example/reset-password?token={token}",
        body_html="",
        arrived_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        message_id="<m1@target.invalid>",
    )])


def _resp(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


@pytest.mark.django_db
def test_reuse_succeeds_emits_finding() -> None:
    """First /reset-password = 200, second /reset-password with the
    SAME token also = 200 → Finding(reset_token_reuse, HIGH, high)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=_email_with_token("abc123")), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.reset_token_reuse.runner.complete_reset",
               side_effect=[_resp(200), _resp(200)]):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_reset_token_reuse"
    assert f.severity == "high"
    assert f.confidence == "high"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["first_consumption_status"] == 200
    assert f.data["second_consumption_status"] == 200
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_second_use_rejected_no_finding() -> None:
    """First /reset-password = 200, second = 400 (token invalidated)
    → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=_email_with_token("abc123")), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.reset_token_reuse.runner.complete_reset",
               side_effect=[_resp(200), _resp(400)]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_first_consumption_fails_no_finding() -> None:
    """First /reset-password = 400 → can't probe reuse → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=_email_with_token("abc123")), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.reset_token_reuse.runner.complete_reset",
               side_effect=[_resp(400), _resp(200)]) as comp_p:
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()
    # Second consumption MUST not have fired.
    assert comp_p.call_count == 1


@pytest.mark.django_db
def test_first_complete_reset_transport_error() -> None:
    """complete_reset returns None on first call → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=_email_with_token("abc123")), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.reset_token_reuse.runner.complete_reset",
               return_value=None):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_second_complete_reset_transport_error() -> None:
    """Second complete_reset returns None → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=_email_with_token("abc123")), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=True), \
         patch("apps.stubs.reset_token_reuse.runner.complete_reset",
               side_effect=[_resp(200), None]):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_no_email_received_emits_refusal() -> None:
    """request_reset succeeds but mailbox times out → AUTH_FIXTURE_
    REQUIRED detail=no_reset_email_received."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=FakeMailbox()), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=True):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_email_received"


@pytest.mark.django_db
def test_request_reset_fails_emits_refusal() -> None:
    """request_reset returns False (target rejected forgot-password)
    → AUTH_FIXTURE_REQUIRED detail=no_reset_email_received."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.6")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.reset_token_reuse.runner.load_mailbox_backend",
               return_value=FakeMailbox()), \
         patch("apps.stubs.reset_token_reuse.runner.fetch_and_find_reset_form",
               return_value=_outcome()), \
         patch("apps.stubs.reset_token_reuse.runner.request_reset",
               return_value=False):
        run(scan_run, target_run)
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_email_received"
