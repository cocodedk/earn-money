"""End-to-end tests for stub 2.17 (oauth-account-linking)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from apps.findings.models import Finding
from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.loader import Program, get_registry
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._test_factories import seed_target_run
from apps.stubs.oauth_account_linking.runner import run

_MODULE = "apps.stubs.oauth_account_linking.runner"


def _program(knob_on=True, accounts=None) -> Program:
    return Program(
        platform="local", slug="oauth-account-linking-lab",
        scope=Scope(
            platform="local", slug="oauth-account-linking-lab",
            policy="rate-limited-OK",
            in_scope=["oauth-account-linking-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_oauth_probes=knob_on,
            allow_active_login_probes=True,
            authorized_test_accounts=accounts or ["user_a"],
        ),
    )


def _link_redirect_response():
    r = MagicMock()
    r.status_code = 302
    r.request = MagicMock()
    r.request.method = "GET"
    r.url = "http://oauth-account-linking-lab:3000/auth/link/start"
    r.text = ""
    r.headers = {
        "Location": "http://oauth-account-linking-lab:3000/oauth/authorize-mock"
                    "?client_id=link-client&response_type=code&redirect_uri=http://localhost/cb"
    }
    return r


def _no_oauth_response():
    r = MagicMock()
    r.status_code = 200
    r.request = MagicMock()
    r.request.method = "GET"
    r.url = "http://oauth-account-linking-lab:3000/settings/connections"
    r.text = '{"linkedProviders":[]}'
    r.headers = {}
    return r


def _login_client(ok=True):
    client = MagicMock()
    login = MagicMock()
    login.status_code = 200 if ok else 401
    login.json.return_value = {"token": "tok-user-a", "userId": "user_a"}
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.return_value = login
    return client


@pytest.mark.django_db
def test_missing_state_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=_link_redirect_response()):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.17").exists()


@pytest.mark.django_db
def test_no_link_ui_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=_no_oauth_response()):
                run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.17").exists()


@pytest.mark.django_db
def test_login_failure_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client(ok=False)):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_OAUTH_ACCOUNT_LINK_URL", "http://oauth-account-linking-lab:3000")
    monkeypatch.setenv("FIXTURE_OAUTH_CLIENT_SECRET", "fixture-value")
    scan_run, target_run = seed_target_run(host="oauth-account-linking-lab", stub_slug="2.17")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=None):
                run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
