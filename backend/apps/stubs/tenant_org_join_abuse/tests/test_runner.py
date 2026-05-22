"""End-to-end tests for stub 2.22 (tenant-org-join-abuse) runner."""
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
from apps.stubs.tenant_org_join_abuse.runner import run

_MODULE = "apps.stubs.tenant_org_join_abuse.runner"


def _program(*, knob_on: bool = True, accounts: list[str] | None = None) -> Program:
    return Program(
        platform="local", slug="tenant-org-join-abuse-lab",
        scope=Scope(
            platform="local", slug="tenant-org-join-abuse-lab",
            policy="rate-limited-OK",
            in_scope=["tenant-org-join-abuse-lab"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=30,
            allow_registration_probes=knob_on,
            authorized_test_accounts=accounts or ["outside"],
        ),
    )


def _login_client(ok: bool = True) -> MagicMock:
    client = MagicMock()
    login = MagicMock()
    login.status_code = 200 if ok else 401
    login.json.return_value = {"token": "tok-outside", "userId": "outside"}
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.return_value = login
    return client


def _join_success_resp() -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.request = MagicMock()
    r.request.method = "POST"
    r.text = '{"TENANT_ORG_JOIN_ABUSE_VULNERABLE":true,"workspace_member":true}'
    r.headers = {}
    return r


def _join_rejected_resp() -> MagicMock:
    r = MagicMock()
    r.status_code = 403
    r.request = MagicMock()
    r.request.method = "POST"
    r.text = '{"TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED":true}'
    r.headers = {}
    return r


def _surface_resp() -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.request = MagicMock()
    r.request.method = "GET"
    r.text = '{"join_url":"/api/workspaces/acme/join","workspace":"acme"}'
    r.headers = {}
    return r


@pytest.mark.django_db
def test_unauthorized_join_creates_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_TENANT_ID", "acme")
    monkeypatch.setenv("FIXTURE_TENANT_LAB_URL", "http://tenant-org-join-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="tenant-org-join-abuse-lab", stub_slug="2.22")
    responses = iter([_surface_resp(), _join_success_resp()])
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", side_effect=lambda _r: next(responses)):
                run(scan_run, target_run)
    assert Finding.objects.filter(scan_run=scan_run, stub_slug="2.22").exists()


@pytest.mark.django_db
def test_invite_required_no_finding(monkeypatch):
    monkeypatch.setenv("FIXTURE_TENANT_ID", "acme")
    monkeypatch.setenv("FIXTURE_TENANT_LAB_URL", "http://tenant-org-join-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="tenant-org-join-abuse-lab", stub_slug="2.22")
    responses = iter([_surface_resp(), _join_rejected_resp()])
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", side_effect=lambda _r: next(responses)):
                run(scan_run, target_run)
    assert not Finding.objects.filter(scan_run=scan_run, stub_slug="2.22").exists()


@pytest.mark.django_db
def test_login_failure_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_TENANT_ID", "acme")
    monkeypatch.setenv("FIXTURE_TENANT_LAB_URL", "http://tenant-org-join-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="tenant-org-join-abuse-lab", stub_slug="2.22")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client(ok=False)):
            run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_on_surface_probe_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_TENANT_ID", "acme")
    monkeypatch.setenv("FIXTURE_TENANT_LAB_URL", "http://tenant-org-join-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="tenant-org-join-abuse-lab", stub_slug="2.22")
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", return_value=None):
                run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()


@pytest.mark.django_db
def test_transport_error_on_join_probe_emits_refusal(monkeypatch):
    monkeypatch.setenv("FIXTURE_TENANT_ID", "acme")
    monkeypatch.setenv("FIXTURE_TENANT_LAB_URL", "http://tenant-org-join-abuse-lab:3000")
    scan_run, target_run = seed_target_run(host="tenant-org-join-abuse-lab", stub_slug="2.22")
    responses = iter([_surface_resp(), None])
    with patch.object(get_registry(), "find_for_host", return_value=_program()):
        with patch(f"{_MODULE}.httpx.Client", return_value=_login_client()):
            with patch(f"{_MODULE}.submit_probe", side_effect=lambda _r: next(responses)):
                run(scan_run, target_run)
    assert Event.objects.filter(
        scan_run=scan_run, type=EventType.AUTH_PROBE_REFUSED,
    ).exists()
