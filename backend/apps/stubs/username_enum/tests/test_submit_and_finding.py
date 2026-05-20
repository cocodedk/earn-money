"""Tests for stub 2.1's submit + diff + Finding emission chunk.

The runner sends invalid + (optional) valid control probes, normalizes
the responses, runs diff(), and emits a Finding when differentiators
are present.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.username_enum.runner import run


def _program(*, accounts: list[str] | None = None) -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=True,
            authorized_test_accounts=accounts or [],
        ),
    )


def _mock_response(*, status: int = 200, body: str = "",
                   content_type: str = "text/html",
                   url: str = "https://x.example/login") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.headers = {"content-type": content_type}
    r.url = url
    return r


_LOGIN_HTML = (
    "<html><body>"
    '<form method="POST" action="https://x.example/login">'
    '<input name="email">'
    '<input name="password" type="password">'
    "</form></body></html>"
)


def _set_up_login_target(scan_run, target_run):
    """Stage the discovery response + mock submit responses for one test."""
    return _mock_response(body=_LOGIN_HTML, url="https://x.example/")


@pytest.mark.django_db
def test_finding_emitted_when_responses_differ() -> None:
    """Two probes against the same form return different statuses
    (401 vs 404) — runner emits a Finding with category
    `auth_username_enum`."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])

    discovery = _set_up_login_target(scan_run, target_run)
    invalid_resp = _mock_response(status=404, body="user not found")
    valid_resp = _mock_response(status=401, body="incorrect password")

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs.username_enum.fetcher.Client") as fetch_cls, \
         patch("apps.stubs.username_enum.submit.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = discovery
        submit_client = submit_cls.return_value.__enter__.return_value
        submit_client.send.side_effect = [invalid_resp, valid_resp]
        run(scan_run, target_run)

    finding = Finding.objects.get(
        scan_run=scan_run, category="auth_username_enum",
    )
    assert finding.data["differentiators_count"] >= 1
    assert finding.confidence == "medium"
    # AUTH_FINDING_CANDIDATE event also fires
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_no_finding_when_responses_identical() -> None:
    """Two probes return the same status + body → no differentiators →
    no Finding emitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])

    discovery = _set_up_login_target(scan_run, target_run)
    identical = _mock_response(status=401, body="invalid credentials")
    # send.side_effect needs 2 separate calls returning same shape
    invalid_resp = _mock_response(status=401, body="invalid credentials")
    valid_resp = _mock_response(status=401, body="invalid credentials")

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs.username_enum.fetcher.Client") as fetch_cls, \
         patch("apps.stubs.username_enum.submit.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = discovery
        submit_cls.return_value.__enter__.return_value.send.side_effect = [
            invalid_resp, valid_resp,
        ]
        run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_invalid_only_probe_emits_candidate_when_unique_signal() -> None:
    """No valid identifier available, but invalid probe returns
    explicit 'user not found' → candidate / low confidence per
    spec 2.1 §6."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=[])  # no scoped valid id

    discovery = _set_up_login_target(scan_run, target_run)
    invalid_resp = _mock_response(status=404, body="user not found")

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs.username_enum.fetcher.Client") as fetch_cls, \
         patch("apps.stubs.username_enum.submit.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = discovery
        submit_cls.return_value.__enter__.return_value.send.return_value = (
            invalid_resp
        )
        run(scan_run, target_run)

    finding = Finding.objects.get(
        scan_run=scan_run, category="auth_username_enum",
    )
    assert finding.confidence == "low"
    assert finding.data["valid_identifier_used"] is False


@pytest.mark.django_db
def test_captcha_abort_prevents_finding() -> None:
    """CAPTCHA in the invalid probe response → no Finding emitted;
    AUTH_PROBE_REFUSED event records the abort instead."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.1")
    prog = _program(accounts=["valid@example.invalid"])

    discovery = _set_up_login_target(scan_run, target_run)
    captcha_resp = _mock_response(
        status=200, body="<html><body>Please complete the CAPTCHA</body></html>",
    )

    with patch.object(get_registry(), "find_for_host", return_value=prog), \
         patch("apps.stubs.username_enum.fetcher.Client") as fetch_cls, \
         patch("apps.stubs.username_enum.submit.Client") as submit_cls:
        fetch_cls.return_value.__enter__.return_value.get.return_value = discovery
        submit_cls.return_value.__enter__.return_value.send.return_value = (
            captcha_resp
        )
        run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run).exists()
