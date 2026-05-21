"""End-to-end detection tests for stub 2.8 (reset-poisoning)."""
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
from apps.stubs.reset_poisoning.runner import SCANNER_POISON_HOST, run


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
        patch("apps.stubs.reset_poisoning.runner.load_mailbox_backend",
              return_value=mailbox),
        patch("apps.stubs.reset_poisoning.runner.fetch_and_find_reset_form",
              return_value=_outcome()),
        patch("apps.stubs.reset_poisoning.runner.request_reset_with_host_header",
              return_value=request_ok),
    ]


def _run(scan_run, target_run, patches):
    for p in patches:
        p.start()
    try:
        run(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()


@pytest.mark.django_db
def test_poisoned_link_emits_finding() -> None:
    """Reset email contains a link with host == SCANNER_POISON_HOST →
    Finding(reset_poisoning, HIGH, high)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    poisoned = f"http://{SCANNER_POISON_HOST}/reset-password?token=abc"
    _run(scan_run, target_run, _wire(_mailbox(f"Click {poisoned}")))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_reset_poisoning"
    assert f.severity == "high"
    assert f.confidence == "high"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["injected_host"] == SCANNER_POISON_HOST
    assert f.data["poisoned_link_host"] == SCANNER_POISON_HOST
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_hardcoded_host_no_finding() -> None:
    """Email contains a link to the target's own host (the safe
    case) → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    safe = "https://x.example/reset-password?token=abc"
    _run(scan_run, target_run, _wire(_mailbox(f"Click {safe}")))
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_no_email_emits_refusal() -> None:
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    _run(scan_run, target_run, _wire(FakeMailbox()))
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_email_received"


@pytest.mark.django_db
def test_request_failure_emits_refusal() -> None:
    """request_reset_with_host_header returns False → AUTH_FIXTURE_
    REQUIRED detail=no_reset_email_received."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    _run(scan_run, target_run, _wire(FakeMailbox(), request_ok=False))
    ev = Event.objects.get(scan_run=scan_run, type=EventType.AUTH_FIXTURE_REQUIRED)
    assert ev.data["detail"] == "no_reset_email_received"


@pytest.mark.django_db
def test_first_url_fallback_used_when_no_reset_substring() -> None:
    """The reset link host matches the poison sentinel but the path
    doesn't contain 'reset' (some targets use opaque paths). The
    fallback `_first_url` extractor still picks it up → Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    poisoned = f"http://{SCANNER_POISON_HOST}/auth/p?t=abc"
    _run(scan_run, target_run, _wire(_mailbox(f"Click {poisoned}")))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.data["poisoned_link_host"] == SCANNER_POISON_HOST


@pytest.mark.django_db
def test_first_url_fallback_in_html_part() -> None:
    """No URL in body_text, but body_html has the poisoned link
    (without 'reset' substring) → Finding via the html-part fallback."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    poisoned = f"http://{SCANNER_POISON_HOST}/auth/p?t=abc"
    _run(scan_run, target_run, _wire(
        _mailbox(body_text="", body_html=f"<a href='{poisoned}'>link</a>"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert f.data["poisoned_link_host"] == SCANNER_POISON_HOST


@pytest.mark.django_db
def test_email_with_no_url_at_all_no_finding() -> None:
    """Email arrives but contains no URL → no Finding emitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.8")
    _run(scan_run, target_run, _wire(
        _mailbox(body_text="No link in this body.", body_html=""),
    ))
    assert not Finding.objects.filter(scan_run=scan_run).exists()
