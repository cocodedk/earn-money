"""Tests for stub 2.1 runner budget + probe-check + valid-norm paths.

Covers uncovered branches:
- break when forms exceed max_forms budget
- check_can_probe returns UNSAFE_METHOD refusal
- valid probe returns None → valid_norm set to None
- valid_norm is None + body has no "not found" signal
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


# Three forms on the page — exceeds max_forms=2 so the third is skipped
_THREE_FORMS_HTML = (
    "<html><body>"
    '<form method="POST" action="https://x.example/login">'
    '<input name="email"><input name="password" type="password"></form>'
    '<form method="POST" action="https://x.example/signup">'
    '<input name="email"><input name="password" type="password"></form>'
    '<form method="POST" action="https://x.example/recover">'
    '<input name="email"></form>'
    "</body></html>"
)

# GET form with a password field → UNSAFE_METHOD refusal
_GET_PASSWORD_HTML = (
    "<html><body>"
    '<form method="GET" action="https://x.example/login">'
    '<input name="email"><input name="password" type="password"></form>'
    "</body></html>"
)

# Login form with a generic "wrong credentials" body — no "not found"
_LOGIN_HTML = (
    "<html><body>"
    '<form method="POST" action="https://x.example/login">'
    '<input name="email"><input name="password" type="password"></form>'
    "</body></html>"
)


@pytest.mark.django_db
def test_forms_beyond_budget_break_loop() -> None:
    """Three auth forms discovered, budget max_forms=2 → loop breaks
    after two forms; the third is never processed."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program()
    discovery_resp = _mock_response(
        body=_THREE_FORMS_HTML, url="https://x.example/",
    )
    invalid_resp = _mock_response(status=401, body="bad credentials")

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs._shared.auth.discovery.Client") as fetch_cls, \
         patch("apps.stubs._shared.auth.requests.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = (
            discovery_resp
        )
        submit_cls.return_value.__enter__.return_value.send.return_value = (
            invalid_resp
        )
        run(scan_run, target_run)

    # Budget capped at 2 forms → exactly 2 submits (one invalid probe per form)
    assert submit_cls.return_value.__enter__.return_value.send.call_count == 2
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_unsafe_method_get_password_form_emits_refused() -> None:
    """A GET form with a password field → check_can_probe returns
    UNSAFE_METHOD → record_refusal fires."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])
    discovery_resp = _mock_response(
        body=_GET_PASSWORD_HTML, url="https://x.example/",
    )

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs._shared.auth.discovery.Client") as fetch_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = (
            discovery_resp
        )
        run(scan_run, target_run)
    ev = Event.objects.get(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    )
    assert ev.data["reason"] == "unsafe_method"


@pytest.mark.django_db
def test_valid_probe_transport_error_falls_back_to_invalid_only() -> None:
    """When the valid probe returns None (transport error), valid_norm
    is set to None and the runner falls back to invalid-only.
    With a generic 'bad credentials' body (no 'not found'), no finding
    is emitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])
    discovery_resp = _mock_response(body=_LOGIN_HTML, url="https://x.example/")
    invalid_resp = _mock_response(status=401, body="bad credentials")

    call_count = [0]

    def _send(request):
        call_count[0] += 1
        if call_count[0] == 1:
            return invalid_resp
        return None  # valid probe → transport error

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs._shared.auth.discovery.Client") as fetch_cls, \
         patch("apps.stubs._shared.auth.requests.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = (
            discovery_resp
        )
        submit_cls.return_value.__enter__.return_value.send.side_effect = _send
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_valid_probe_captcha_falls_back_to_invalid_only_no_finding() -> None:
    """When the valid probe returns a CAPTCHA-abort response, valid_norm
    is set to None and the runner falls back to invalid-only.
    Generic body → no finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])
    discovery_resp = _mock_response(body=_LOGIN_HTML, url="https://x.example/")
    invalid_resp = _mock_response(status=401, body="bad credentials")
    captcha_resp = _mock_response(
        status=200,
        body="<html><body>Please complete the CAPTCHA</body></html>",
    )

    call_count = [0]

    def _send(request):
        call_count[0] += 1
        if call_count[0] == 1:
            return invalid_resp
        return captcha_resp  # valid probe → captcha abort

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs._shared.auth.discovery.Client") as fetch_cls, \
         patch("apps.stubs._shared.auth.requests.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = (
            discovery_resp
        )
        submit_cls.return_value.__enter__.return_value.send.side_effect = _send
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()
