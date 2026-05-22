"""Safety-floor tests for stub 2.1's submit path — codex P1 findings:

- P1.1 off-scope form action_url: never POST creds off-program.
- P1.3 per-probe rate-limit: acquire_for(program) for every submit.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding
from apps.programs.loader import get_registry
from apps.stubs._test_factories import seed_target_run
from apps.stubs.username_enum.runner import run
from apps.stubs.username_enum.tests._helpers import _mock_response, _program


_IN_SCOPE_LOGIN_HTML = (
    "<html><body>"
    '<form method="POST" action="https://x.example/login">'
    '<input name="email">'
    '<input name="password" type="password">'
    "</form></body></html>"
)


@pytest.mark.django_db
def test_off_scope_form_action_url_skipped() -> None:
    """Discovery returns a login form whose `action_url` points off-
    scope (SSO/IdP host). The runner must NOT POST credentials there —
    enforce_scope raises OutOfScope on the action_url and the probe is
    skipped. No Finding, OUT_OF_SCOPE_REJECTED emitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])
    off_scope_html = (
        "<html><body>"
        '<form method="POST" action="https://attacker.example/sso">'
        '<input name="email">'
        '<input name="password" type="password">'
        "</form></body></html>"
    )
    discovery = _mock_response(body=off_scope_html, url="https://x.example/")

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs._shared.auth.discovery.Client") as fetch_cls, \
         patch("apps.stubs._shared.auth.requests.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = discovery
        run(scan_run, target_run)
        submit_cls.return_value.__enter__.return_value.send.assert_not_called()
    assert not Finding.objects.filter(scan_run=scan_run).exists()
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
    ).exists()


@pytest.mark.django_db
def test_rate_limit_acquired_per_probe() -> None:
    """Each probe acquires one RoE token via `acquire_for(program)`.
    The two-probe invalid+valid pair → 2 calls."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])
    discovery = _mock_response(body=_IN_SCOPE_LOGIN_HTML, url="https://x.example/")
    invalid_resp = _mock_response(status=404, body="user not found")
    valid_resp = _mock_response(status=401, body="incorrect password")
    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs._shared.auth.discovery.Client") as fetch_cls, \
         patch("apps.stubs._shared.auth.requests.Client") as submit_cls, \
         patch("apps.stubs.username_enum.runner.acquire_for") as acquire_p:
        fetch_cls.return_value.__enter__.return_value.get.return_value = discovery
        submit_cls.return_value.__enter__.return_value.send.side_effect = [
            invalid_resp, valid_resp,
        ]
        run(scan_run, target_run)
    assert acquire_p.call_count == 2
