"""Codex P1 — path-style token redaction tests for stub 2.7.

Split out of `test_redaction.py` once path-style coverage grew
past the 200-line file cap. These tests assert the regex handles
both `/keyword/<token>` and `/keyword-<token>` separators across
the compound-keyword family (reset, reset-password, password-
reset, forgot-password, verify, confirm, recover, token).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from apps.findings.models import Finding
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


def _mailbox(body_text: str) -> FakeMailbox:
    return FakeMailbox(messages=[InboundMessage(
        to_address="scanner@example.invalid",
        from_address="noreply@target.invalid",
        subject="Reset", body_text=body_text, body_html="",
        arrived_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        message_id="<m1@target.invalid>",
    )])


def _wire(mailbox: FakeMailbox):
    return [
        patch.object(get_registry(), "find_for_host", return_value=_program()),
        patch("apps.stubs.weak_reset_expiry.runner.load_mailbox_backend",
              return_value=mailbox),
        patch("apps.stubs.weak_reset_expiry.runner.fetch_and_find_reset_form",
              return_value=DiscoveryOutcome(
                  form=_RESET_FORM, final_url=_RESET_FORM.action_url, error=None,
              )),
        patch("apps.stubs.weak_reset_expiry.runner.request_reset",
              return_value=True),
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
def test_slash_separator_redacted() -> None:
    """`/reset/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/reset/SECRET-TOKEN-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN-XYZ" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]


@pytest.mark.django_db
def test_hyphen_separator_redacted() -> None:
    """`/reset-<token>` — hyphen separator on the plain keyword.
    Codex pass-3 P1 caught the regression here."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/reset-SECRET-TOKEN to confirm"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_verify_hyphen_separator_redacted() -> None:
    """`/verify-<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/verify-UNIQUE-NONCE"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "UNIQUE-NONCE" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_verify_slash_separator_redacted() -> None:
    """`/verify/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Visit https://x.example/verify/UNIQUE-NONCE to confirm."),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "UNIQUE-NONCE" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_compound_reset_password_redacted() -> None:
    """`/reset-password/<token>` shape (Express/Rails/Django style)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/reset-password/SECRET-TOKEN-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN-XYZ" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]


@pytest.mark.django_db
def test_reversed_password_reset_redacted() -> None:
    """`/password-reset/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/password-reset/SECRET-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-XYZ" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_forgot_password_redacted() -> None:
    """`/forgot-password/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/forgot-password/SECRET-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-XYZ" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_non_token_url_preserved() -> None:
    """A non-token URL stays intact in the snippet."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Visit https://x.example/home for more info."),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "https://x.example/home" in f.data["body_snippet"]
