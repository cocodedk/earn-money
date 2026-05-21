"""End-to-end detection tests for stub 2.15 (oauth-missing-state)."""
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
from apps.stubs.oauth_missing_state.runner import run


_MODULE = "apps.stubs.oauth_missing_state.runner"


def _program(knob_on: bool = True) -> Program:
    return Program(
        platform="local", slug="oauth-state-missing",
        scope=Scope(
            platform="local", slug="oauth-state-missing",
            policy="rate-limited-OK",
            in_scope=["oauth-state-missing"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            authorized_test_accounts=["scanner@example.invalid"],
        ),
    )


def _redirect_response(location: str, status: int = 302):
    r = MagicMock()
    r.status_code = status
    r.headers = {"Location": location} if location else {}
    r.text = ""
    return r


@pytest.mark.django_db
def test_missing_state_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    vuln_location = (
        "http://oauth-state-missing:3000/oauth/authorize"
        "?client_id=test-client&redirect_uri=http%3A%2F%2Flocalhost%2Fcb&response_type=code&scope=openid"
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.submit_probe",
                   return_value=_redirect_response(vuln_location)):
            run(scan_run, target_run)

    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()
    finding = Finding.objects.get(scan_run=scan_run, stub_slug="2.15")
    assert finding.confidence == "high"


@pytest.mark.django_db
def test_state_present_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    safe_location = (
        "http://oauth-state-missing:3000/oauth/authorize"
        "?client_id=test-client&redirect_uri=http%3A%2F%2Flocalhost%2Fcb"
        "&response_type=code&scope=openid&state=abc123"
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.submit_probe",
                   return_value=_redirect_response(safe_location)):
            run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()


@pytest.mark.django_db
def test_non_oauth_redirect_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.submit_probe",
                   return_value=_redirect_response("http://oauth-state-missing:3000/login")):
            run(scan_run, target_run)

    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.15").exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-state-missing", stub_slug="2.15")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.submit_probe", return_value=None):
            run(scan_run, target_run)

    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
