"""End-to-end tests for stub 2.3 (missing-lockout) detection."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.missing_lockout.runner import run
from apps.stubs._shared.auth.discovery import FetchOutcome


_LOGIN_HTML = """
<html><body>
  <form action="/login" method="POST">
    <input type="text" name="username">
    <input type="password" name="password">
    <input type="hidden" name="csrf" value="abc">
    <button type="submit">Login</button>
  </form>
</body></html>
"""


def _program() -> Program:
    return Program(
        platform="local", slug="dvwa",
        scope=Scope(
            platform="local", slug="dvwa",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=True,
            authorized_test_accounts=["scanner@example.invalid"],
        ),
    )


def _outcome() -> FetchOutcome:
    return FetchOutcome(
        ok=True, status=200, body=_LOGIN_HTML,
        content_type="text/html", final_url="https://x.example/",
        error=None,
    )


def _resp(*, body: str = "Invalid credentials") -> MagicMock:
    r = MagicMock()
    r.text = body
    return r


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch) -> None:
    """Skip the 750ms inter-attempt sleep in tests."""
    monkeypatch.setattr(
        "apps.stubs.missing_lockout.runner.time.sleep",
        lambda _s: None,
    )


@pytest.mark.django_db
def test_no_lockout_emits_finding() -> None:
    """5 failed attempts complete with no abort → Finding(HIGH,
    auth_missing_lockout, candidate, requires_manual_review)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.missing_lockout.runner.submit_probe",
               return_value=_resp()):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_missing_lockout"
    assert f.severity == "high"
    assert f.confidence == "medium"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["failed_attempts"] == 5
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_lockout_signal_stops_loop_no_finding() -> None:
    """Server returns a rate-limit body → loop stops early, no
    Finding emitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    locked = _resp(body="Too many requests — please wait")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.missing_lockout.runner.submit_probe",
               return_value=locked):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_transport_failure_mid_loop_no_finding() -> None:
    """submit_probe returns None on attempt 3 → partial loop, no
    Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.3")
    sequence = [_resp(), _resp(), None, _resp(), _resp()]
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.missing_lockout.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.missing_lockout.runner.submit_probe",
               side_effect=sequence):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()
