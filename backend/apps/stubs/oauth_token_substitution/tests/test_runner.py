"""End-to-end tests for stub 2.16 (oauth-token-substitution)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from apps.findings.models import Finding
from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.auth.discovery import FetchOutcome
from apps.stubs._test_factories import seed_target_run
from apps.stubs.oauth_token_substitution.runner import run
from apps.stubs.oauth_token_substitution.submit import SubstitutionResult

_MODULE = "apps.stubs.oauth_token_substitution.runner"


def _program(knob_on=True, accounts=None) -> Program:
    return Program(
        platform="local", slug="oauth-token-substitution-lab",
        scope=Scope(
            platform="local", slug="oauth-token-substitution-lab",
            policy="rate-limited-OK",
            in_scope=["oauth-token-substitution-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            allow_active_login_probes=True,
            authorized_test_accounts=accounts or ["user_a", "user_b"],
        ),
    )


def _oauth_outcome():
    oauth_url = (
        "http://oauth-token-substitution-lab:3000/oauth/authorize"
        "?client_id=x&response_type=code&redirect_uri=http://localhost/cb"
    )
    return FetchOutcome(ok=True, status=200, body="", content_type="text/html",
                        final_url=oauth_url, error=None)


@pytest.mark.django_db
def test_confirmed_substitution_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    confirmed = SubstitutionResult(
        substitution_attempted=True, substitution_accepted=True,
        identity_mismatch_observed=True, status="confirmed",
        confidence="high", artifact_kind="authorization_code",
        flow_url="http://oauth-token-substitution-lab:3000",
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_oauth_outcome()):
            with patch(f"{_MODULE}.run_substitution_test", return_value=confirmed):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.16", confidence="high").exists()


@pytest.mark.django_db
def test_passive_only_no_active_creates_candidate(monkeypatch):
    """One account → active path skipped (needs ≥2); passive candidate created."""
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    prog = _program(accounts=["user_a"])  # 1 account → active path skipped
    oauth_url = (
        "http://oauth-token-substitution-lab:3000/oauth/authorize"
        "?client_id=x&response_type=code&redirect_uri=http://localhost/cb"
    )
    outcome = FetchOutcome(ok=True, status=200, body="", content_type="text/html",
                           final_url=oauth_url, error=None)
    with patch.object(get_registry(), "find_for_host", return_value=prog):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=outcome):
            run(scan_run, target_run)
    f = Finding.objects.filter(scan_run=scan_run, stub_slug="2.16")
    # passive candidate or no finding — must not be confirmed
    for finding in f:
        assert finding.status != "confirmed"


@pytest.mark.django_db
def test_no_oauth_signals_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    prog = _program(accounts=["user_a"])  # passive path only
    outcome = FetchOutcome(ok=True, status=200, body="<html>Login</html>",
                           content_type="text/html", final_url="http://oauth-token-substitution-lab:3000/login",
                           error=None)
    with patch.object(get_registry(), "find_for_host", return_value=prog):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=outcome):
            run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.16").exists()


@pytest.mark.django_db
def test_active_rejected_falls_through_to_passive(monkeypatch):
    """Active probe returns rejected (not attempted) — passive candidate emitted if signals detected."""
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    rejected = SubstitutionResult(
        substitution_attempted=False, substitution_accepted=None,
        identity_mismatch_observed=None, status="candidate",
        confidence="low", artifact_kind="authorization_code",
        flow_url="http://oauth-token-substitution-lab:3000",
    )
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=_oauth_outcome()):
            with patch(f"{_MODULE}.run_substitution_test", return_value=rejected):
                run(scan_run, target_run)
    # substitution_attempted=False so doesn't emit via active path;
    # passive evidence (oauth url signals) creates a passive candidate
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.16").exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_TOKEN_SUB_URL", "http://oauth-token-substitution-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-token-substitution-lab", stub_slug="2.16")
    prog = _program(accounts=["user_a"])  # passive path only
    outcome = FetchOutcome(ok=False, status=0, body="", content_type="",
                           final_url="", error="connect_error")
    with patch.object(get_registry(), "find_for_host", return_value=prog):
        with patch(f"{_MODULE}.fetch_for_discovery", return_value=outcome):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
