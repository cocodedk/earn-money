"""Codex P1 — query-string token redaction tests for stub 2.7.

`?token=...`, `?code=...`, etc. Path-style redaction tests live
in `test_redaction_path.py` (split per the 200-line file cap).
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
def test_query_token_redacted() -> None:
    """Query-string `?token=<value>` → `?token=<redacted>`."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/reset?token=SECRET-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-XYZ" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]


@pytest.mark.django_db
def test_query_code_param_redacted() -> None:
    """Alternative query-param name `code` is also redacted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    _run(scan_run, target_run, _wire(
        _mailbox("Click https://x.example/reset?code=SECRET-CODE"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-CODE" not in f.data["body_snippet"]
