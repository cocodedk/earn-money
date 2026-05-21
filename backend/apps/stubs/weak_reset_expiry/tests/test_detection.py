"""End-to-end detection tests for stub 2.7 (weak-reset-expiry)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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
from apps.stubs.weak_reset_expiry.runner import run


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


def _mailbox(body_text: str, body_html: str = "") -> FakeMailbox:
    return FakeMailbox(messages=[InboundMessage(
        to_address="scanner@example.invalid",
        from_address="noreply@target.invalid",
        subject="Reset",
        body_text=body_text, body_html=body_html,
        arrived_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        message_id="<m1@target.invalid>",
    )])


def _wire(mailbox: FakeMailbox, request_ok: bool = True):
    return [
        patch.object(get_registry(), "find_for_host", return_value=_program()),
        patch("apps.stubs.weak_reset_expiry.runner.load_mailbox_backend",
              return_value=mailbox),
        patch("apps.stubs.weak_reset_expiry.runner.fetch_and_find_reset_form",
              return_value=_outcome()),
        patch("apps.stubs.weak_reset_expiry.runner.request_reset",
              return_value=request_ok),
    ]


@pytest.mark.django_db
def test_no_expiry_marker_emits_finding() -> None:
    """Reset email body has no expiry phrase → Finding(MEDIUM, low,
    candidate, requires_manual_review)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    mailbox = _mailbox(
        "Click here to reset: https://x.example/reset?token=abc",
    )
    patches = _wire(mailbox)
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_weak_reset_expiry"
    assert f.severity == "medium"
    assert f.confidence == "low"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["requires_manual_review"] is True
    # Codex P1: token must NOT appear raw in persisted snippet.
    assert "abc" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_expires_in_phrase_suppresses_finding() -> None:
    """Body contains 'expires in 30 minutes' → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    mailbox = _mailbox(
        "Click here to reset. This link expires in 30 minutes.",
    )
    patches = _wire(mailbox)
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_valid_for_phrase_suppresses_finding() -> None:
    """Body contains 'valid for' → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    mailbox = _mailbox("The link is valid for the next 24 hours.")
    patches = _wire(mailbox)
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_marker_only_in_html_part_suppresses_finding() -> None:
    """body_text has no marker but body_html does → no Finding
    (combined search reads both parts)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    mailbox = _mailbox(
        body_text="Click to reset: https://x.example/reset?token=abc",
        body_html=(
            "<p>Reset link expires within the next 15 minutes.</p>"
        ),
    )
    patches = _wire(mailbox)
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_no_email_received_emits_refusal() -> None:
    """Mailbox times out → AUTH_FIXTURE_REQUIRED detail=no_reset_
    email_received."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    mailbox = FakeMailbox()
    patches = _wire(mailbox)
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_email_received"


@pytest.mark.django_db
def test_request_reset_fails_emits_refusal() -> None:
    """request_reset returns False → AUTH_FIXTURE_REQUIRED detail=
    no_reset_email_received."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    mailbox = FakeMailbox()
    patches = _wire(mailbox, request_ok=False)
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_email_received"


