"""Shared fixtures for the stub 2.7 redaction tests.

Both `test_redaction.py` (query strings) and `test_redaction_path.py`
(path-style tokens) need the same Program / AuthForm / mailbox /
discovery wiring. Extracted here so each test file stays under the
200-line cap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs._shared.auth.mailbox import FakeMailbox, InboundMessage
from apps.stubs.predictable_reset_token.discovery import DiscoveryOutcome
from apps.stubs.weak_reset_expiry.runner import run as _run_runner


def program() -> Program:
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


RESET_FORM = AuthForm(
    method="POST",
    action_url="https://x.example/forgot-password",
    content_type="application/x-www-form-urlencoded",
    identifier_field="email", password_field=None,
    hidden_fields={}, flow_hint="password_reset",
)


def mailbox(body_text: str) -> FakeMailbox:
    return FakeMailbox(messages=[InboundMessage(
        to_address="scanner@example.invalid",
        from_address="noreply@target.invalid",
        subject="Reset", body_text=body_text, body_html="",
        arrived_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        message_id="<m1@target.invalid>",
    )])


def wire(box: FakeMailbox):
    return [
        patch.object(get_registry(), "find_for_host", return_value=program()),
        patch("apps.stubs.weak_reset_expiry.runner.load_mailbox_backend",
              return_value=box),
        patch("apps.stubs.weak_reset_expiry.runner.fetch_and_find_reset_form",
              return_value=DiscoveryOutcome(
                  form=RESET_FORM, final_url=RESET_FORM.action_url, error=None,
              )),
        patch("apps.stubs.weak_reset_expiry.runner.request_reset",
              return_value=True),
    ]


def run_with(scan_run, target_run, patches):
    for p in patches:
        p.start()
    try:
        _run_runner(scan_run, target_run)
    finally:
        for p in patches:
            p.stop()
