"""End-to-end tests for stub 2.4 (weak-rate-limiting)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.events.models import Event
from apps.events.types import EventType
from apps.findings.models import Finding, FindingStatus
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.discovery import FetchOutcome
from apps.stubs._test_factories import seed_target_run
from apps.stubs.weak_rate_limiting.runner import run


_LOGIN_HTML = """
<html><body>
  <form action="/login" method="POST">
    <input type="text" name="username">
    <input type="password" name="password">
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
        ),
    )


def _outcome() -> FetchOutcome:
    return FetchOutcome(
        ok=True, status=200, body=_LOGIN_HTML,
        content_type="text/html", final_url="https://x.example/",
        error=None,
    )


def _resp(
    *, status: int = 200,
    body: str = "Invalid credentials",
    headers: dict | None = None,
) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.headers = headers or {}
    return r


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch) -> None:
    """Skip the 250ms inter-attempt sleep in tests."""
    monkeypatch.setattr(
        "apps.stubs.weak_rate_limiting.runner.time.sleep",
        lambda _s: None,
    )


@pytest.mark.django_db
def test_no_throttle_emits_finding() -> None:
    """6 failed attempts with no throttle signal → Finding(MEDIUM,
    auth_weak_rate_limiting, candidate, requires_manual_review)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.4")
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_rate_limiting.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.weak_rate_limiting.runner.submit_probe",
               return_value=_resp()):
        run(scan_run, target_run)
    f = Finding.objects.get(scan_run=scan_run)
    assert f.category == "auth_weak_rate_limiting"
    assert f.severity == "medium"
    assert f.confidence == "medium"
    assert f.status == FindingStatus.CANDIDATE
    assert f.data["attempts_sent"] == 6
    assert f.data["requires_manual_review"] is True
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_FINDING_CANDIDATE,
    ).exists()


@pytest.mark.django_db
def test_status_429_stops_loop_no_finding() -> None:
    """Server returns 429 on attempt 3 → loop stops early, no
    Finding emitted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.4")
    sequence = [_resp(), _resp(), _resp(status=429, body="rate-limit"),
                _resp(), _resp(), _resp()]
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_rate_limiting.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.weak_rate_limiting.runner.submit_probe",
               side_effect=sequence):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_retry_after_header_stops_loop_no_finding() -> None:
    """Server emits Retry-After header → throttle observed, no
    Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.4")
    retry = _resp(status=200, headers={"Retry-After": "60"})
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_rate_limiting.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.weak_rate_limiting.runner.submit_probe",
               return_value=retry):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()


@pytest.mark.django_db
def test_transport_failure_no_finding() -> None:
    """submit_probe returns None mid-loop → no Finding."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.4")
    sequence = [_resp(), _resp(), None, _resp(), _resp(), _resp()]
    with patch.object(get_registry(), "find_for_host", return_value=_program()), \
         patch("apps.stubs.weak_rate_limiting.runner.fetch_for_discovery",
               return_value=_outcome()), \
         patch("apps.stubs.weak_rate_limiting.runner.submit_probe",
               side_effect=sequence):
        run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run).exists()
